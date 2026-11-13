// components/fuzzy_select.js: NiceGUI's own select.js (nicegui/elements/select.js, NiceGUI 4.0.0) with ONE change:
// findFilteredOptions ranks by fuzzy match (fuzzy_match.js) instead of keeping options that contain the typed text,
// and filterFn then scrolls the list to its best match.
// Everything else is NiceGUI's, unchanged, so the element behaves exactly as ui.select does.  If NiceGUI is upgraded,
// diff this against its select.js again (tests/test_fuzzyselect.py fails when the two have drifted apart).
export default {
  props: ["options"],
  template: `
    <q-select
      ref="qRef"
      :options="filteredOptions"
      @filter="filterFn"
      @popup-show="addClass"
      @popup-hide="removeClass"
      @input-value="forwardInputValue"
      @update:model-value="forwardModelValue"
    >
      <template v-for="(_, slot) in $slots" v-slot:[slot]="slotProps">
        <slot :name="slot" v-bind="slotProps || {}" />
      </template>
    </q-select>
  `,
  emits: ["input-value", "update:model-value"],
  data() {
    return {
      initialOptions: this.options,
      filteredOptions: this.options,
      modelValueChanged: false,
    };
  },
  methods: {
    forwardModelValue(...args) {
      this.modelValueChanged = true;
      this.$emit("update:model-value", ...args);
    },
    async forwardInputValue(value) {
      this.modelValueChanged = false;
      await this.$nextTick(); // wait for a possible "update:model-value" event indicating a selection
      if (!this.modelValueChanged) {
        this.$emit("input-value", value); // suppress selection-induced events which would re-trigger filtering (#4420)
      }
    },
    filterFn(val, update, abort) {
      update(
        () => (this.filteredOptions = val ? this.findFilteredOptions() : this.initialOptions),
        // Show the list from its best match: left alone, the menu stays scrolled to the option that was selected.
        (ref) => {
          if (val && ref.options.length > 0) {
            ref.setOptionIndex(-1);
            ref.moveOptionSelection(1, true);
          }
        },
      );
    },
    findFilteredOptions() {
      const typed = this.$el.querySelector("input[type=search]")?.value ?? "";
      if (!typed.trim()) return this.initialOptions;
      // mtFuzzy comes from fuzzy_match.js, linked in the page head; without it, fall back to what NiceGUI does.
      if (window.mtFuzzy) return window.mtFuzzy.filter(typed, this.initialOptions);
      const needle = typed.toLocaleLowerCase();
      return this.initialOptions.filter((v) => String(v.label).toLocaleLowerCase().indexOf(needle) > -1);
    },
    addClass() {
      // prevent the page from scrolling when the select popup is closed (#5031)
      document.documentElement.classList.add("nicegui-select-popup-open");
    },
    async removeClass() {
      await this.$nextTick();
      document.documentElement.classList.remove("nicegui-select-popup-open");
    },
  },
  updated() {
    if (!this.$attrs.multiple) return;
    const newFilteredOptions = this.findFilteredOptions();
    if (newFilteredOptions.length !== this.filteredOptions.length) {
      this.filteredOptions = newFilteredOptions;
    }
  },
  unmounted() {
    this.removeClass();
  },
  watch: {
    options: {
      handler(newOptions) {
        this.initialOptions = newOptions;
        this.filteredOptions = newOptions;
      },
      immediate: true,
    },
  },
};

from nicegui import ui

# A list of common monospaced fonts to query
MONO_FONTS = [
    "Consolas",
    "Monaco",
    "Inconsolata",
    "Fira Code",
    "Courier New",
    "Source Code Pro",
    "Ubuntu Mono",
    "Menlo",
    "JetBrains Mono",
]


async def check_fonts():
    # JavaScript logic using the modern, native font loading API
    js_code = f"""
    () => {{
        const fonts = {MONO_FONTS};
        const available = [];
        
        for (const font of fonts) {{
            // document.fonts.check tests if the font is available/loaded.
            // We pass a generic fallback so it has a baseline comparison context.
            if (document.fonts.check(`12px "${{font}}"`)) {{
                available.push(font);
            }}
        }}
        return available;
    }}
    """

    # Run the JS on the browser side and get the array back in Python
    detected_fonts = await ui.run_javascript(js_code)

    results_container.clear()
    with results_container:
        if detected_fonts:
            ui.label("Successfully Detected Fonts:").classes("font-bold text-lg text-green-600 mb-2")
            for font in detected_fonts:
                ui.label(font).style(f'font-family: "{font}", monospace; font-size: 1.1rem;')
        else:
            ui.label("No whitelisted fonts were detected by the browser API.").classes("text-amber-600")


# NiceGUI UI Layout
ui.markdown("### Local Monospace Font Detector (API Method)")
ui.button("Scan Browser Fonts", on_click=check_fonts).props("color=primary")
results_container = ui.element("div").classes("p-4 border rounded-lg mt-4 bg-gray-50 min-h-[100px]")

ui.run()

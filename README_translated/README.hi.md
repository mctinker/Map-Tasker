<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../documentation_images/maptasker_logo_dark.png">
    <img src="../documentation_images/maptasker_logo_light.png" alt="MapTasker">
  </picture>
</p>

<div align="center">

![PyPI](https://img.shields.io/pypi/v/maptasker)
![PyPI - Downloads](https://img.shields.io/pypi/dm/maptasker?color=green&label=downloads)
![Downloads](https://static.pepy.tech/personalized-badge/maptasker?period=total&units=international_system&left_color=grey&right_color=green&left_text=downloads)
![Python](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fmctinker%2FMap-Tasker%2Frefs%2Fheads%2FMaster%2Fpyproject.toml)
![PyPI - License](https://img.shields.io/pypi/l/maptasker)
![](https://tokei.rs/b1/github/mctinker/Map-Tasker)
[![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[!["Buy Me A Coffee"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)

</div>

<p align="center">
  <b>Read this in:</b>
  <a href="../README.md">English</a> •
  <a href="README.zh-CN.md">简体中文</a> •
  <a href="README.es.md">Español</a> •
  <a href="README.hi.md">हिन्दी</a> •
  <a href="README.fr.md">Français</a> •
  <a href="README.ar.md">العربية</a> •
  <a href="README.de.md">Deutsch</a> •
  <a href="README.da.md">Dansk</a> •
  <a href="README.fi.md">Suomi</a> •
  <a href="README.ru.md">Русский</a> •
  <a href="README.ko.md">한국어</a> •
  <a href="README.ja.md">日本語</a>
</p>

---

# MapTasker

> यह अनुवाद स्वचालित रूप से तैयार किया गया है। किसी भी अंतर की स्थिति में, [मूल अंग्रेज़ी README](../README.md) ही मान्य होगा।

## अपने (Mac/Windows 11/Linux) डेस्कटॉप ब्राउज़र में, Tasker के बैकअप या एक्सपोर्ट की गई XML फ़ाइल के आधार पर, Tasker के Project(s), Profile(s), Task(s), और Scene(s) को देखें/संपादित करें/विश्लेषित करें

कॉन्फ़िगरेशन मैप...
![MapTasker कॉन्फ़िगरेशन मैप: एक Project, उसके Profiles और Tasks को रंग-कोडित, इंडेंट की गई रूपरेखा के रूप में दिखाया गया है, जिसमें हर Task के नीचे उसके क्रमांकित actions और उनकी सेटिंग्स सूचीबद्ध हैं](../documentation_images/intro.png)

डायग्राम मैप...
![MapTasker डायग्राम मैप: एक Project और उसके Profiles को बॉक्स के रूप में दिखाया गया है, नीचे उनके Tasks हैं, और रेखाएँ दिखाती हैं कि कौन-सा Task किस Task को कॉल कर रहा है, जिसमें एक कॉल पथ को हाइलाइट किया गया है](../documentation_images/Introd.png)

[[अधिक उदाहरण]](<https://github.com/mctinker/Map-Tasker/wiki#sample-output>)

यह [Tasker](https://tasker.joaoapps.com/) के समर्थन में बनाया गया एक एप्लिकेशन है, जिसे वेब ब्राउज़र में चलाने के लिए डिज़ाइन किया गया है (देखें [नोट 1](#1))।

मुझे लगा कि मेरे Tasker के Projects/Profiles/Tasks/Scenes अब संभाल पाना मुश्किल हो गए हैं, और मेरा फ़ोन इतना छोटा था कि उनमें नेविगेट करना आसान नहीं था। इसलिए मैंने एक Python प्रोग्राम लिखा, जो मेरे द्वारा अपनी डेस्कटॉप ड्राइव पर सहेजी गई Tasker बैकअप XML फ़ाइल के आधार पर, मेरे पूरे कॉन्फ़िगरेशन का एक संपूर्ण मैप मेरे वेब ब्राउज़र में प्रदान करता है।

समय के साथ, मैंने इस मैप को और बेहतर बनाया, इसमें कई अतिरिक्त विकल्प जोड़े, जिनमें Tasker ऑब्जेक्ट्स को संपादित करने और Tasker कॉन्फ़िगरेशन का गहन विश्लेषण प्रदान करने की क्षमता शामिल है।

Tasker बैकअप या अन्य Tasker एक्सपोर्ट की गई XML को आप मैन्युअल रूप से अपने PC/Mac/Linux/क्लाउड ड्राइव पर अपलोड कर सकते हैं, या यह प्रोग्राम इसे सीधे आपके Android डिवाइस से भी प्राप्त कर सकता है (देखें [नोट 2](#2))।

## विशेषताएँ (Features)

- आउटपुट का विस्तार स्तर आपकी पसंद का—एक संक्षिप्त अवलोकन से लेकर आपके कॉन्फ़िगरेशन के बहुत विस्तृत स्तर तक।
- केवल एक Project, Profile, या Task प्रदर्शित करें।
- Profile और Task की शर्तों को शामिल/बाहर रखें: States, Events, आदि।
- सब कुछ सीधे stream करें, या सभी फ़ील्ड को align करके आउटपुट को "सुंदर" बनाएं।
- दिखावट बदलें: 'light' या 'dark' मोड चुनें।
- अपनी पसंद के monospaced फ़ॉन्ट में आउटपुट लें, और Project, Profile और Task के नामों को italic, bold, highlighted और/या underscored बनाकर उन पर ज़ोर दें।
- अपने मूड के अनुसार आउटपुट के विभिन्न पहलुओं से जुड़े रंगों को बदलें।
- TaskerNet विवरण और/या Tasker की प्राथमिकताएँ (preferences) शामिल करें।
- जटिल कॉन्फ़िगरेशन के लिए, वैकल्पिक रूप से अपने Projects, Profiles, Tasks और Scenes के हाइपरलिंक्स की एक डायरेक्टरी शामिल करें।
- अपने पूरे Tasker कॉन्फ़िगरेशन का डायग्राम, साथ ही एक Task Flow प्रदर्शित करें।
- कमांड लाइन या GUI इंटरफ़ेस।
- कॉन्फ़िगरेशन मैपिंग के लिए एक्सपोर्ट की गई XML का उपयोग करें, या XML को सीधे अपने Android डिवाइस से प्राप्त करें।
- Projects, Profiles, Tasks और Scenes को वापस अपने Android डिवाइस पर Tasker में भेजें।
- रनटाइम सेटिंग्स को सहेजें और पुनर्स्थापित करें।
- उन Tasks की पहचान करें जिनमें बहुत अधिक 'actions' हैं, और जिन्हें संभवतः कई Tasks में विभाजित किया जाना चाहिए।
- किसी विशेष Project, Profile, Task या Scene का विश्लेषण करने के लिए AI विश्लेषण विकल्प, जिसमें सर्वर-आधारित ChatGPT/Claude/Gemini या लोकल-आधारित Llama (Ollama के माध्यम से) समर्थित मॉडल का उपयोग किया जा सकता है।
- परिणामों को सीधे GUI के भीतर प्रदर्शित करें: (कॉन्फ़िगरेशन) Map View, Tree View, और Diagram View।
- स्वचालित अपडेट पहचान और नए संस्करणों की वैकल्पिक इंस्टॉलेशन।
- बेहतर खोज और संरचित 'Find/Replace'।
- Projects, Profiles, Tasks, और Scenes जोड़ें और संपादित करें (देखें [नोट 6](#6))।
- किसी विशेष तारीख़ से हुए बदलावों की सूची देखें।
- किसी Project, Profile, Task या Scene को उस TaskerNet share से लिंक करें जिससे वह आया है, जब उसके लेखक एक नया संस्करण प्रकाशित करें तो सूचना प्राप्त करें, और उनके बदलावों को एक-एक करके अपनाएं।
- Tasker XML के साथ-साथ पूरे कॉन्फ़िगरेशन में मौजूद अनेक variables की स्थिति का विश्लेषण करें।
- किसी XML फ़ाइल की तुलना लोड की गई XML से करें।

## प्रोग्राम निर्भरताएँ (Dependencies)

### - Python संस्करण 3.11 या उच्चतर

### - Tasker की पूरी या आंशिक XML फ़ाइल: backup.xml या अन्य Tasker एक्सपोर्ट की गई XML फ़ाइल

&nbsp;&nbsp;&nbsp;आपको अपने डेस्कटॉप पर अपनी Tasker एक्सपोर्ट की गई XML फ़ाइल (जैसे backup.xml) को ढूँढने और चुनने के लिए कहा जाएगा, जो Tasker वर्शन 5 या वर्शन 6 द्वारा बनाई गई हो। वैकल्पिक रूप से, आप इसे सीधे अपने Android डिवाइस से भी प्राप्त कर सकते हैं (देखें [नोट 2](#2))।

### - AI विश्लेषण

&nbsp;&nbsp;&nbsp;सर्वर-आधारित विश्लेषण के लिए एक वैध API key, और/या लोकल विश्लेषण के लिए Ollama इंस्टॉल होना आवश्यक है (देखें [नोट 3](#3))।


## इंस्टॉलेशन

इस प्रोग्राम और इसकी सभी आवश्यक चीज़ों के लिए लगभग 230MB जगह चाहिए होगी। इसे एक वर्चुअल एनवायरनमेंट में इंस्टॉल करने की सलाह दी जाती है (विकल्प 2)।

- Terminal/Command Prompt में निम्न में से कोई एक कमांड डालकर MapTasker को इंस्टॉल करें:

     ```python -m pip install maptasker -U```
                 ...या...
     ```uv add maptasker```

- इसे किसी वर्चुअल एनवायरनमेंट में इंस्टॉल करने के लिए, Terminal/command prompt में निम्न कमांड डालें:

  pip के माध्यम से...
  - `cd xxx`, जहाँ 'xxx' वह डायरेक्टरी है जिसमें आप वर्चुअल एनवायरनमेंट सेट करना चाहते हैं।
  - `python -m venv venv`
  - वर्चुअल एनवायरनमेंट को एक्टिवेट करें...
    MAC/linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `venv\Scripts\activate`
  - `pip install maptasker`

  ...या...
  
  uv के माध्यम से...
  - `cd xxx`, जहाँ 'xxx' वह डायरेक्टरी है जिसमें आप वर्चुअल एनवायरनमेंट सेट करना चाहते हैं।
  - `uv venv`
  - वर्चुअल एनवायरनमेंट को एक्टिवेट करें...
    MAC/linux: `source {directory path to 'xxx'}/venv/bin/activate`
    Windows: `venv\Scripts\activate`
  - `uv pip install maptasker`

- AI विश्लेषण सुविधाओं के लिए अतिरिक्त लाइब्रेरी (OpenAI, Anthropic, Google और Ollama) चाहिए होती हैं। MapTasker इन्हें आपके लिए इंस्टॉल नहीं करता; यदि आप इन्हें चाहते हैं, तो इसके बजाय `ai` extra के साथ MapTasker इंस्टॉल करें:

     ```python -m pip install "maptasker[ai]" -U```
                 ...या...
     ```uv add "maptasker[ai]"```
  
## उपयोग (Usage)

- कमांड डालें:

     ```maptasker```
     ...या यदि वर्चुअल एनवायरनमेंट प्रबंधित करने के लिए uv का उपयोग कर रहे हैं...
     ```uv run maptasker```

### कमांड लाइन से रिपोर्ट्स

Health Check, Compare, Changes Since, Export और एक फ़ोल्डर watch बिना किसी विंडो के चलते हैं, जिससे किसी रात की Tasker बैकअप की जाँच स्वचालित रूप से की जा सकती है (`cron`, Task Scheduler, `launchd` या किसी CI job से):

```
maptasker -healthcheck -file backup.xml                 # किसी बैकअप में समस्याएँ
maptasker -compare older.xml newer.xml                  # दो बैकअप के बीच का अंतर
maptasker -changes_since week -file backup.xml          # क्या बदला: today, week, month, all, एक तारीख़, या 3d
maptasker -export map -format md -file backup.xml       # Map (या diagram) को md, json या pdf के रूप में
maptasker -watch ~/TaskerBackups                        # हर नए बैकअप को history में रिकॉर्ड करें
```

- **`-file`** एक बैकअप, या एक फ़ोल्डर (जिसमें सबसे नई `.xml` फ़ाइल उपयोग की जाती है) ले सकता है। `-outdir` यह चुनता है कि फ़ाइलें कहाँ लिखी जाएँ, और `-save` रिपोर्ट को भी फ़ाइल के रूप में सहेजता है, जैसा विंडो करती है।
- **केवल रिपोर्ट, और सिर्फ़ रिपोर्ट, standard output में जाती है**; बाकी सब कुछ standard error में जाता है, ताकि `maptasker -healthcheck -file backup.xml > report.txt` एक साफ़ रिपोर्ट दे।
- **Exit codes** किसी स्क्रिप्ट को परिणाम के आधार पर कार्य करने देते हैं:

  | Code | अर्थ |
  |---|---|
  | 0 | पूरा हो गया, और रिपोर्ट करने के लिए कुछ नहीं था |
  | 10 | रिपोर्ट में कुछ मिला: Health Check त्रुटियाँ (warnings शामिल करने के लिए `-fail_on warning`, उन्हें नज़रअंदाज़ करने के लिए `-fail_on never`), या अंतर |
  | 11 | `-changes_since` के पास तुलना के लिए पहले का कोई कॉन्फ़िगरेशन नहीं था (पहली बार चलने पर history शुरू होती है) |
  | 1 | प्रोग्राम त्रुटि |
  | 2 | कोई फ़ाइल नहीं लिखी जा सकी (एक ऐसा `-outdir` फ़ोल्डर शामिल है जिसका उपयोग नहीं किया जा सकता), या आउटपुट नहीं बनाया जा सका |
  | 3 | फ़ाइल एक वैध Tasker बैकअप नहीं है |
  | 5 | माँगा गया एक Project, Profile या Task (`-project`, `-profile` या `-task`) नहीं मिला |
  | 6 | कोई फ़ाइल नहीं दी गई, या फ़ाइल या फ़ोल्डर मौजूद नहीं है |
  | 7 | अमान्य विकल्प, जैसे ग़लत रंग, कोई अज्ञात `-fail_on` मान, या किसी फ़ाइल की तुलना स्वयं से करना |
  | 8 | Tasker सर्वर चला रहे Android डिवाइस को किया गया रिक्वेस्ट असफल हो गया |

- **History।** जो भी बैकअप लोड किया जाता है वह configuration history में रिकॉर्ड हो जाता है, जिसे ही `-changes_since` पढ़ता है। `-watch FOLDER` उस `FOLDER` में दिखने वाले हर नए, पूर्ण बैकअप को फ़ाइल की तारीख़ के अनुसार रिकॉर्ड करता है, जिससे वे दिन भी history में शामिल हो जाते हैं जब आप MapTasker खोलते भी नहीं; किसी scheduled job के लिए `-watch FOLDER -once` केवल एक बार जाँच करता है। History को उस डायरेक्टरी में `MapTasker_Timeline` नाम के फ़ोल्डर में रखा जाता है जिससे MapTasker चलाया जाता है, इसलिए किसी scheduled job को `-history_dir` का उपयोग करके उसी फ़ोल्डर को इंगित करना चाहिए जिसे विंडो उपयोग करती है।
- **बाकी कुछ नहीं बदलता।** ये रन कभी भी ब्राउज़र नहीं खोलते और कभी भी उन सेटिंग्स को नहीं बदलते जिन्हें विंडो सहेजे रखती है।

## प्रोग्राम आउटपुट

MapTasker डेस्कटॉप और Android डिवाइस दोनों पर कई आउटपुट फ़ाइलें बनाता है।

MapTasker द्वारा जनरेट किए गए आउटपुट की पूरी सूची के लिए [wiki](https://github.com/mctinker/Map-Tasker/wiki/Generated-Output) देखें।


## अधिक जानकारी: [[रनटाइम विकल्प]](https://github.com/mctinker/Map-Tasker/wiki/Runtime-Options)&nbsp;&nbsp;&nbsp;[[रनटाइम विकल्पों के उदाहरण]](https://github.com/mctinker/Map-Tasker/wiki/Sample-Runtime-Options)&nbsp;&nbsp;&nbsp;[[नमूना आउटपुट]](https://github.com/mctinker/Map-Tasker/wiki#sample-output)

## प्रोजेक्ट संरचना

मुख्य फ़ाइलों और उनके उद्देश्य का संक्षिप्त अवलोकन:

- `maptasker/`: मुख्य एप्लिकेशन कोड शामिल है।
  - `maptasker/src/`: MapTasker के लॉजिक के लिए मुख्य Python सोर्स फ़ाइलें।
  - `maptasker/assets/`: एप्लिकेशन द्वारा उपयोग किए जाने वाले स्टैटिक एसेट्स जैसे आइकन, इमेज और JSON डेटा।
  - `maptasker/locale`: अनुवादों के लिए भाषा फ़ाइलें।
- `documentation_images/`: इस README और अन्य दस्तावेज़ीकरण में उपयोग की गई इमेज।
- `tools/`: विकास के दौरान उपयोग की जाने वाली utilities।
- `tests/`: कोड की गुणवत्ता सुनिश्चित करने के लिए टेस्ट स्क्रिप्ट्स और संबंधित फ़ाइलें शामिल हैं।
- `maptasker/main.py`: `maptasker` कमांड के पीछे का entry point। किसी clone की गई रिपॉज़िटरी से, `python -m maptasker.main` चलाएँ।
- `LICENSE`: प्रोजेक्ट की MIT License फ़ाइल।
- `README.md`: यह फ़ाइल (मूल अंग्रेज़ी)।
- `Changelog.md`: हर संस्करण में किए गए बदलावों का लॉग।
- `pyproject.toml`: प्रोजेक्ट मेटाडेटा और बिल्ड सिस्टम कॉन्फ़िगरेशन।

## लाइसेंस (License)

यह प्रोजेक्ट [MIT License](../LICENSE) के अंतर्गत लाइसेंस प्राप्त है।

MIT License एक अनुमेय (permissive) फ्री सॉफ़्टवेयर लाइसेंस है जो Massachusetts Institute of Technology (MIT) से उत्पन्न हुआ है। एक अनुमेय लाइसेंस होने के कारण, यह पुनः उपयोग (reuse) पर बहुत सीमित प्रतिबंध लगाता है, और इसलिए इसमें लाइसेंस संगतता (compatibility) बहुत अधिक है।

संक्षेप में, इसका अर्थ है कि आप स्वतंत्र हैं:

- **उपयोग करने के लिए**: सॉफ़्टवेयर का किसी भी उद्देश्य (व्यावसायिक या निजी) के लिए उपयोग करें।
- **संशोधित करने के लिए**: सॉफ़्टवेयर को संशोधित करें।
- **वितरित करने के लिए**: मूल या संशोधित सॉफ़्टवेयर को वितरित करें।
- **उप-लाइसेंस देने के लिए**: सॉफ़्टवेयर का उप-लाइसेंस (sublicense) दें।

आपको यह करना होगा:

- **कॉपीराइट शामिल करें**: सॉफ़्टवेयर के किसी भी महत्वपूर्ण हिस्से में मूल कॉपीराइट नोटिस और लाइसेंस को शामिल करें।

सॉफ़्टवेयर "जैसा है" (AS IS) प्रदान किया जाता है, बिना किसी प्रकार की वारंटी के। पूर्ण लाइसेंस टेक्स्ट के लिए, कृपया [LICENSE](../LICENSE) फ़ाइल देखें।

## समस्या निवारण और सामान्य प्रश्न (FAQ)

**प्रश्न: Windows के Notepad में `MapTasker_Map.txt` डायग्राम गलत तरीके से aligned दिखता है।**

उत्तर: Notepad इस फ़ाइल की स्पेसिंग को सही ढंग से हैंडल नहीं कर पाता।

एक अलग text editor जैसे Notepad++, VS Code, या Typepad का उपयोग करने की सलाह दी जाती है (और इसे `.txt` फ़ाइलों के लिए डिफ़ॉल्ट सेट करें)। सुनिश्चित करें कि 'text-wrap' बंद हो और एक monospace फ़ॉन्ट उपयोग किया जा रहा हो।

**प्रश्न: मैं अपने Android डिवाइस से सीधे Tasker XML फ़ाइल कैसे प्राप्त करूँ?**

उत्तर: आवश्यकताएँ:

1- ब्राउज़र और Android डिवाइस एक ही लोकल नेटवर्क पर होने चाहिए।

2- Android डिवाइस पर ['Http Server Example' Tasker Project](https://shorturl.at/bwCD4) इंस्टॉल और सक्रिय होना चाहिए, और सर्वर चल रहा हो।

अधिक जानकारी इस README के "Notes" सेक्शन में उपलब्ध है।

**प्रश्न: चीनी, कोरियाई, या जापानी नामों के लिए डायग्राम connectors गलत तरीके से aligned होते हैं।**

उत्तर: यह diagramming library में इन भाषाओं के font metrics से संबंधित एक ज्ञात समस्या (known issue) है।

**प्रश्न: कुछ Task actions और Profile states/events edit/addition के लिए उपलब्ध क्यों नहीं हैं?

उत्तर: कुछ मामलों में, इन actions, events, या states को ऐसी जानकारी की आवश्यकता होती है जो केवल Android पर और/या Tasker के भीतर ही उपलब्ध होती है। इनके लिए edit की अनुमति देने से एक अपूर्ण Task या Profile बन जाएगा, जिससे Tasker में फ़ेलियर हो सकता है।

## Notes (टिप्पणियाँ)

"समस्या निवारण और सामान्य प्रश्न" सेक्शन में बताए गए कुछ बिंदुओं के विवरण, अतिरिक्त संदर्भ के लिए यहाँ दिए गए हैं।

### 1
**Windows 11 विशिष्ट जानकारी:**

- केवल Windows 11 समर्थित है। Windows के किसी भी पुराने संस्करण का समर्थन नहीं किया जाता।
- Notepad में `MapTasker_Map.txt` के डिस्प्ले से जुड़ी समस्याओं के लिए, Typepad जैसे किसी अन्य text editor का उपयोग करें और इसे `.txt` फ़ाइलों के लिए डिफ़ॉल्ट सेट करें।

### 2
**Android से सीधे XML प्राप्त करना:**

Tasker XML फ़ाइल को सीधे प्राप्त करने के लिए:

- सुनिश्चित करें कि डेस्कटॉप और Android दोनों डिवाइस एक ही लोकल नेटवर्क पर हों और Tasker चल रहा हो।
- ['Http Server Example' Tasker Project](https://shorturl.at/bwCD4) Android डिवाइस पर इंस्टॉल और सक्रिय होना चाहिए, और सर्वर चल रहा हो। "Update GD HTTP Info" Task को चलाना याद रखें और (केवल पहली बार) पूछे जाने पर अपनी Google Drive ID दर्ज करें।
- प्राप्त होने के बाद, XML आपके डेस्कटॉप पर सहेजी जाती है और जब तक इसमें बदलाव न हो, इसे बार-बार फिर से प्राप्त करने की आवश्यकता नहीं है।

### 3
**AI समर्थन**

AI विश्लेषण केवल GUI के माध्यम से उपलब्ध है। आप केवल एक ही Project, Profile, Task, या Scene का उपयोग करके विश्लेषण चला सकते हैं। सर्वर-आधारित OpenAi (ChatGPT), Gemini, और Anthropic के साथ-साथ लोकल-आधारित Llama मॉडलों का समर्थन उपलब्ध है।

Llama आधारित मॉडल [Ollama](https://ollama.com/) के माध्यम से समर्थित हैं, जिसे आपको अपने डेस्कटॉप पर सर्वर सेट करने के लिए मैन्युअल रूप से डाउनलोड, इंस्टॉल और एक बार चलाना होगा। यदि Llama मॉडल पहले से लोड नहीं हैं, तो MapTasker आपके लिए उन्हें डायनामिक रूप से लोड कर देगा।

सहायक AI मॉड्यूल MapTasker इंस्टॉल करते समय डिफ़ॉल्ट रूप से इंस्टॉल नहीं होते। इसके बजाय, वे विशेष AI रिक्वेस्ट के पहली बार उपयोग किए जाने पर डायनामिक रूप से इंस्टॉल होते हैं। इस तरह, यदि आप AI का उपयोग करने की योजना नहीं बनाते हैं, तो आपको इसका ओवरहेड नहीं उठाना पड़ता।


## एप्लिकेशन संपादन और विश्लेषण संबंधी सावधानियाँ
**MapTasker संपादन और विश्लेषण संबंधी सावधानियाँ**

विवरण के लिए [Caveats](https://github.com/mctinker/Map-Tasker/blob/Master/caveats.txt) दस्तावेज़ देखें।


## टू-डू लिस्ट (किसी विशेष क्रम में नहीं)

- [x] Readiness Check

- [x] अतिरिक्त plugins का समर्थन

- [x] निर्भरताओं (dependencies) के साथ इम्पोर्ट (Import with Dependencies)

- [ ] बाकी Tasker preferences को मैप करना

- [x] Task Stepper: किसी Task को action-by-action "dry-run" करना, यह दिखाते हुए कि कौन-सी If, For और Goto branches चलती हैं और हर variable में क्या मान है

- [x] Live Run Monitor: फ़ोन पर कौन-से Profiles और Tasks ट्रिगर हो रहे हैं इसे लाइव स्ट्रीम करना और उन्हें Diagram view में हाइलाइट करना

- [ ] दो बैकअप का उनके किसी सामान्य पूर्वज (common ancestor) के सापेक्ष three-way merge, जिसे conflict-by-conflict हल किया जाए और एक ही चरण में undo किया जा सके

- [x] TaskerNet update tracker: जब आपके उपयोग किए गए share के लेखक एक नया संस्करण प्रकाशित करें तो आपको बताना, उस बदलाव के diff के साथ

- [ ] Personal snippet library: पुनः उपयोग किए जा सकने वाले action sequences, Tasks और Profile templates को सहेजें और उन्हें parameters के साथ insert करें

- [ ] Map में सरल भाषा में व्याख्या: हर Profile और Task का एक AI-लिखित, cached और संपादन योग्य एक-लाइन सारांश

- [x] Missing-resource checker: यह जाँचें कि आपके actions द्वारा संदर्भित फ़ाइलें, फ़ोल्डर, इमेज, साउंड, Scenes और apps अभी भी मौजूद हैं

- [x] जटिलता और trend dashboard: समय के साथ Task की लंबाई, nesting, call-chain depth और findings को ट्रैक करना

- [ ] Documentation site export: एक-दूसरे से लिंक किए गए Markdown या HTML पेजों का एक सेट, हर Project, Profile, Task और Scene के लिए एक, साथ में call diagrams

- [x] Variable rename और scope assistant: किसी variable का नाम बदलें, या किसी global को local बनाएं, हर जगह जहाँ वह उपयोग होता है, और इसे एक ही Undo के रूप में करें

## गोपनीयता विवरण (Privacy Statement)

नीचे सूचीबद्ध (Network Traffic) को छोड़कर, किसी भी तरह की जानकारी नेटवर्क के माध्यम से कैप्चर करके मुझे या किसी अन्य तीसरे पक्ष को नहीं भेजी जाती।

जब आप किसी त्रुटि (error) की रिपोर्ट करते हैं, तो आपसे बहुत संभावना है कि त्रुटि का output log file और आपकी XML फ़ाइल प्रदान करने के लिए कहा जाएगा, जिनका उपयोग केवल प्रोग्राम को debug करने के लिए किया जाएगा और फिर उन्हें तुरंत delete कर दिया जाएगा।

नेटवर्क ट्रैफ़िक इस प्रकार है:

- अपने Android डिवाइस से सीधे XML प्राप्त करते समय लोकल LAN ट्रैफ़िक।
- स्टार्टअप पर दिन में एक बार, यह जाँचने के लिए pypi.com से संपर्क किया जाता है कि कोई नया रिलीज़ उपलब्ध है या नहीं।
- यदि GUI में 'Upgrade' चुना जाता है, तो ('pip' के माध्यम से) pypi.com से प्रोग्राम को अपडेट किया जाता है।
- यदि GUI में "What's New" चुना जाता है, तो '<https://github.com/mctinker/Map-Tasker>' से फ़ाइल 'Changelog.md' पढ़ी जाती है।
- जब किसी भी OpenAi मॉडल के साथ AI विश्लेषण का उपयोग किया जाता है, तो chatgpt.com का उपयोग किया जाता है। MapTasker का आउटपुट विश्लेषण के लिए standard API call के माध्यम से सर्वर पर भेजा जाता है। Claude (Anthropic), और Gemini (Google) के लिए भी यही लागू होता है।
- AI Analysis सुविधा चलाते समय, नए और अपडेट किए गए लोकल AI मॉडल '<https://ollama.com/library>' से लोड किए जाएँगे।
- Task action labels और TaskerNet विवरणों में '<img src=https://...>' HTML टैग के माध्यम से परिभाषित इमेज और वीडियो स्रोत हाइपरलिंक्स को क्लिक किए जाने पर एक्सेस किया जाएगा। उदाहरण: imggur.com, Youtube, Dropbox, Google Drive, आदि।

## योगदान (Contributing)

योगदान का स्वागत है! MapTasker में योगदान देने के कुछ तरीके यहाँ दिए गए हैं:

**बग रिपोर्ट करना:**

- यदि आपको कोई bug मिलता है, तो कृपया [GitHub Issues page](https://github.com/mctinker/Map-Tasker/issues) पर एक issue खोलें।
- जितना संभव हो उतना विवरण शामिल करें:
  - bug को reproduce करने के चरण।
  - अपेक्षित व्यवहार (expected behavior) और वास्तविक व्यवहार (actual behavior)।
  - आपका operating system और Python version।
  - MapTasker version।
  - आपकी Tasker XML फ़ाइल के संबंधित हिस्से (यदि लागू हो, और यह सुनिश्चित करें कि इसमें कोई संवेदनशील जानकारी शामिल न हो)।
  - यदि `-debug` विकल्प के साथ generate की गई हो तो `maptasker.log` फ़ाइल।

**सुधार सुझाना:**

- GitHub पर एक issue खोलें, अपने सुझाव का विवरण देते हुए।
- use case समझाएँ और यह सुधार क्यों फ़ायदेमंद होगा।

**Pull Requests:**

- यदि आप कोड के साथ योगदान देना चाहते हैं:
    1. रिपॉज़िटरी को Fork करें।
    2. अपने feature या bug fix के लिए एक नई branch बनाएं (जैसे, `feature/new-output-format` या `fix/xml-parsing-error`)।
    3. अपने बदलाव करें।
    4. सुनिश्चित करें कि आपका कोड Black code style का पालन करता है (जैसा badge में दिखाया गया है)।
    5. यदि लागू हो, तो अपने बदलावों के लिए `tests/` डायरेक्टरी में tests जोड़ें।
    6. सुनिश्चित करें कि सभी tests pass हों।
    7. `Master` branch पर एक pull request सबमिट करें।

**Coding Style:**

- यह प्रोजेक्ट code formatting के लिए [Ruff](https://docs.astral.sh/ruff/formatter/) का उपयोग करता है। कृपया सुनिश्चित करें कि आपके योगदान Ruff के साथ formatted हैं।

MapTasker को बेहतर बनाने में आपकी मदद के लिए हम आभारी हैं!

## ज्ञात समस्याएँ (Known Issues)

- यदि नाम चीनी, कोरियाई, या जापानी में हैं तो डायग्राम connectors गलत तरीके से aligned होते हैं।
- सभी Task actions और Profile state/event editing समर्थित नहीं हैं, क्योंकि कुछ के लिए ऐसी जानकारी चाहिए जो केवल एक Android डिवाइस पर उपलब्ध होती है।

## योगदानकर्ता (Contributions)

[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)

[©Connor Talbot 2021, Clippy के लिए](https://github.com/con-dog/clippy)

[Ollama](https://ollama.com/), [OpenAi](https://openai.com/), [Claude AI](https://claude.ai), [Gemini AI](https://gemini.google.com/)

[NiceGui](https://nicegui.io/)

[!["Buy Me A Coffee"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)

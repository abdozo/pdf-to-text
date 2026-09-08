# خطة تنفيذ دفعات Gemini الديناميكية والاستريمنج

تاريخ الخطة: 2026-09-09

هذه وثيقة تسليم مستقلة لمحادثة تنفيذ جديدة. المطلوب تنفيذها في تطبيق ورّاق، لا إجراء بحث جديد من الصفر. نطاقها هو اختيار حجم دفعة الصور ديناميكيًا لكل موديل، احترام حصص المشروع، وبث تقدم الدفعة الطويلة. لا تشمل إصلاحات محرر النص الغني أو تنسيق بطاقة الدفعة، فقد عولجت في مسار آخر.

## النتيجة المطلوبة

عند اختيار أي موديل تحويل مدعوم، يجب أن يحدد ورّاق أكبر دفعة آمنة اعتمادًا على:

1. حد إدخال الموديل وحد إخراجه للطلب الواحد.
2. توكنات الصور والتعليمات الفعلية قبل الإرسال.
3. تقدير إخراج الصفحات اعتمادًا على نتائج سابقة للموديل ونوع المستند.
4. حصص مشروع Gemini الحالية: RPM وinput TPM وRPD.
5. حجم payload الفعلي وحد النقل الخاص بالمسار المستخدم.
6. حد اختياري يضعه المستخدم لعدد الصفحات.

يجب ألا يحتوي القرار على حالة خاصة لـ`gemini-3.5-flash-lite`، وألا يفترض أن `65_536` أو `250_000` يصلحان لكل موديل أو مشروع.

## الحقائق المؤكدة التي يبنى عليها التنفيذ

### CSV الخاص بـGoogle AI Studio

ملف `aistudio.csv` هو لقطة استخدام وحصص لمشروع معين. صيغة الخانات هي `المستهلك / الحد`:

| العمود | المعنى الصحيح |
| --- | --- |
| RPM | الطلبات في الدقيقة |
| TPM | توكنات الإدخال في الدقيقة، وليس حد الطلب الواحد وليس توكنات الإخراج |
| RPD | الطلبات في اليوم |

مثلًا `1.06K / 250K` يعني أن المشروع استهلك نحو 1.06 ألف من حصة قدرها 250 ألف توكن إدخال في الدقيقة. و`2 / 5` يعني طلبين من خمسة في الدقيقة.

الحدود الظاهرة في اللقطة المرفقة لموديلات التحويل هي:

| اسم AI Studio | RPM | input TPM | RPD |
| --- | ---: | ---: | ---: |
| Gemini 2.5 Flash-Lite | 10 | 250,000 | 20 |
| Gemini 2.5 Flash | 5 | 250,000 | 20 |
| Gemini 3 Flash | 5 | 250,000 | 20 |
| Gemini 3.1 Flash-Lite | 15 | 250,000 | 500 |
| Gemini 3.5 Flash-Lite | 15 | 250,000 | 500 |
| Gemini 3.5 Flash | 5 | 250,000 | 20 |
| Gemini 3.6 Flash | 5 | 250,000 | 20 |
| Gemini 3.7 Flash | 5 | 250,000 | 20 |
| Gemini 3.8 Flash | 5 | 250,000 | 20 |

صفوف `0 / 0` مثل Gemini 2.5 Pro وGemini 3.1 Pro تعني أن هذا المشروع لا يملك حصة لها في اللقطة. لا تعني أن نافذة سياق الموديل صفر. كما يجب تجاهل أقسام Live API وTTS وتوليد الصور وgrounding في مسار نسخ الصفحات.

هذه الأرقام ليست ثوابت عالمية. Google تطبقها على المشروع لا على API key، وقد تتغير باختلاف tier وحالة الحساب والموديل. واجهة Models API لا تعيد RPM أو TPM أو RPD. المصدر العملي لها في الإصدار الأول هو استيراد CSV من AI Studio أو إدخالها يدويًا.

### حدود الطلب الواحد

واجهة `models.get` تعيد لكل موديل:

- `input_token_limit`
- `output_token_limit`
- `version`
- `display_name`
- `supported_actions`
- معلومات التفكير والتوليد المتاحة

هذه هي القيم التي يجب استخدامها لسعة الطلب. واجهة Models API لا تعيد حصص المشروع ولا تعرض حقولًا صريحة لدعم الصور أو Structured Outputs، لذلك يبقى للتطبيق سجل توافق صغير خاص بموديلات OCR.

وقت كتابة الخطة، تعرض وثائق Google لكل موديلات التحويل النصية الحالية في ورّاق حد إدخال 1,048,576 وحد إخراج 65,536، وتؤكد دعم الصور أو PDF وStructured Outputs. هذا تحقق للحالة الحالية فقط. يجب أن يقرأ التطبيق القيم وقت التشغيل ويخزنها مؤقتًا، حتى يعمل تلقائيًا إذا اختلف موديل لاحقًا.

نسخة `google-genai` الحالية، 1.75.0، تحتوي حقول `input_token_limit` و`output_token_limit` و`supported_actions`. لا تجعل ترقية SDK شرطًا لهذه الميزة، لكن اختبر adapter مقابل النسخة المقيدة في `pyproject.toml` و`requirements-desktop.txt`.

### الصور وحجم الطلب

تذكر Google حدًا نظريًا قدره 3,600 صورة في الطلب، لكنه ليس حجم دفعة عمليًا للنسخ. حد الإخراج وTPM وحجم payload والزمن وجودة الاستخراج ستتدخل قبله.

وثائق Google الحالية تذكر 100MB للبيانات inline عمومًا، بينما صفحة الصور الخاصة بمسار `generateContent` القديم ما زالت توصي بأقل من 20MB شامل التعليمات. بما أن ورّاق يرسل صور JPEG inline عبر `generateContent`، استخدم 20MB سقفًا محافظًا في `TransportPolicy` للإصدار الأول، واجعله إعدادًا مركزيًا مرتبطًا بالـendpoint لا بالموديل. لا ترفعه إلى 100MB إلا بعد اختبار حي موثق للمسار والـSDK المستخدمين.

## مشكلات الوضع الحالي

- `waraq/gemini_client.py` يثبت `max_output_tokens=16384` للصفحة والدفعة، رغم اختلاف السقف النظري بحسب الموديل.
- `MODEL_DAILY_LIMITS` يخلط قائمة الموديلات المدعومة مع حصة يومية ثابتة وعرض الواجهة.
- `DEFAULT_QUOTAS` في `waraq/database.py` يعامل لقطة الحصص كحقائق ثابتة.
- الحصص مخزنة تحت `key_id`، مع أن Google تحاسب المشروع. مفتاحان للمشروع نفسه يظهران حاليًا كحصتين مستقلتين.
- `ConversionRunner` يقسم الصفحات مقدمًا بحسب `pages_per_request` ولا يعيد التخطيط بعد رؤية التوكنات أو الفشل.
- مسار الدفعة يستخدم `generate_content` ويحفظ الصفحات بعد اكتمال الرد كله.
- 429 يؤدي إلى فشل المهمة بدل انتظار الحصة أو تطبيق backoff منضبط.
- قائمة الموديلات لا تستفيد من حدود الإدخال والإخراج التي تعيدها API.

## التصميم المستهدف

### 1. فصل قدرات الموديل عن حصة المشروع

أضف نموذجين منفصلين:

```text
ModelCapabilities
  model_id
  api_name
  version
  display_name
  input_token_limit
  output_token_limit
  supports_generate_content
  supports_thinking
  supports_image_input
  supports_structured_output
  supports_streaming
  fetched_at
  source

ProjectQuotaProfile
  id
  name
  source
  imported_at
  model_limits[]: model_id, rpm, input_tpm, rpd
```

مصدر حقول التوكنات والتوفر هو `models.list/get`. مصدر دعم الصور وStructured Outputs هو سجل توافق ورّاق، لأن Models API لا يعرضهما صراحة. مصدر RPM وTPM وRPD هو ملف حصة المشروع الذي يدخله المستخدم.

لا تربط الحصة مباشرة بالمفتاح. أضف `quota_profile_id` إلى المفتاح بحيث يمكن لمفتاحين تابعين للمشروع نفسه مشاركة ledger واحدًا. عند ترحيل البيانات الحالية، أنشئ ملف حصة منفصلًا لكل مفتاح حفاظًا على السلوك الحالي، ثم اسمح للمستخدم بضم المفاتيح التي يعرف أنها للمشروع نفسه.

### 2. خدمة metadata ديناميكية

في `GeminiClient` أو adapter مستقل:

1. استدع `models.list` لاكتشاف الموديلات المتاحة التي تدعم `generateContent`.
2. تقاطع النتائج مع سجل موديلات OCR المتوافقة، لا مع جدول الحصص.
3. استخرج حدود الإدخال والإخراج والنسخة من metadata.
4. خزّن النتيجة حسب `model_id + version` مع `fetched_at`.
5. حدّثها عند التحقق من المفتاح، وعند بدء جلسة إذا مر 24 ساعة.
6. عند فشل الشبكة استخدم آخر metadata مخزنة مع وسم `stale`.
7. إذا لم توجد metadata مخزنة، امنع الوضع التلقائي لذلك الموديل واعرض سببًا واضحًا. لا تخترع حدًا.

لا تخمّن Model ID من اسم العرض. استخدم خريطة صريحة مثل `Gemini 3 Flash` إلى `gemini-3-flash-preview`، وراجعها مقابل نتيجة `models.list`.

### 3. استيراد حصة AI Studio

أضف مستورد CSV واختباراته:

1. تحقق من الأعمدة `model-cell`, `category`, `RPM`, `TPM`, `RPD`.
2. اقبل صفوف `Text-out models` فقط.
3. حلل `used / limit` مع دعم `K` و`M` والمسافات والقيم الفارغة.
4. اعرض preview يربط اسم العرض بـModel ID قبل الحفظ.
5. خزّن المقام فقط كحد. البسط لقطة سريعة التقادم ولا يستخدمها planner.
6. اعتبر `0 / 0` عدم توفر للمشروع، لا قدرة موديل صفرية.
7. سجّل المصدر ووقت الاستيراد وحذّر عند قدم الملف.

لا تستخدم scraping لـAI Studio. القراءة الآلية الكاملة للحصص تحتاج تكامل Cloud Quotas وصلاحيات IAM، وهي خارج الإصدار الأول.

### 4. `BatchPlanner` متعدد القيود

أنشئ مكونًا مستقلًا عن UI و`GeminiClient`. مدخلاته:

```text
remaining_pages
model_capabilities
project_quota_profile
local_quota_snapshot
transport_policy
extraction_mode
document_profile
user_max_pages | null
historical_usage
```

يختار أطول prefix من الصفحات يحقق كل الآتي:

```text
counted_input <= input_token_limit * input_headroom
counted_input <= locally_available_input_tpm * tpm_headroom
predicted_output <= output_token_limit * output_headroom
encoded_payload_bytes <= transport_payload_limit
page_count <= user_max_pages              # إن وُضع
```

قيم بداية مقترحة قابلة للتعديل والقياس، وليست حدود Google:

- `input_headroom = 0.80`
- `output_headroom = 0.75`
- `tpm_headroom = 0.80`
- `transport_payload_limit = 20MB` للمسار الحالي

ابدأ من دفعة معايرة صغيرة عند غياب التاريخ، مثل 4 صفحات، ثم كبر الهدف تدريجيًا 4، 8، 16، 24، 32 وما بعدها ما دامت القيود تسمح. لا تجعل هذه السلسلة سقفًا للموديل، بل نقاط نمو محافظة.

ابن request الحقيقي بالصور والتعليمات وschema ثم استخدم `models.count_tokens`. لتقليل استدعاءات العد، اختبر أكبر مرشح أولًا ثم صغره ببحث ثنائي إذا تجاوز حد الإدخال أو TPM. لا تعتمد على حجم JPEG لتقدير توكنات الصورة.

تقدير الإخراج يجب أن يكون خاصًا بـ`model_id + extraction_mode + document_profile`. استخدم المئين 95 لتوكنات الإخراج لكل صفحة مع overhead للـJSON schema. عند غياب التاريخ استخدم نتائج دفعة المعايرة، لا رقمًا عالميًا لصفحة عربية.

احسب `max_output_tokens` هكذا:

```text
requested_output = ceil(predicted_output * request_headroom)
max_output_tokens = min(requested_output, model.output_token_limit)
```

لا تثبته على 16,384 ولا ترسله دائمًا بالسقف الكامل.

### 5. ledger ذري لحصة المشروع

وسع المنظم الحالي ليتابع لكل `quota_profile_id + model_id`:

- عدد طلبات الدقيقة لـRPM.
- مجموع توكنات الإدخال في الدقيقة لـTPM.
- عدد طلبات اليوم لـRPD، مع إعادة الضبط وفق توقيت Google المعلن.

قبل الإرسال، احجز request واحدة و`counted_input` بصورة ذرية. بعد اكتمال الرد، استبدل التقدير بـ`usage_metadata.prompt_token_count` إن توفر. لا تجمع `usage_metadata` من chunks إن كانت القيم تراكمية، بل احتفظ بآخر قيمة غير فارغة ثم اختبر سلوك SDK.

الـledger المحلي لا يرى طلبات برامج أخرى في المشروع. لذلك 429 يظل ممكنًا. عند 429 و503 طبّق exponential backoff مع jitter واحترام `Retry-After` إن توفر، مع سقف محاولات واضح. لا تصغر الدفعة لمجرد 429؛ صغرها عندما يكون السبب توكنات أو payload أو timeout متكررًا.

### 6. الاستريمنج والإخراج المنظم

أضف مسار `generate_content_stream` للدفعات. لا حاجة إلى تحويل الصفحة المفردة أولًا.

1. أرسل request واحدًا بنفس الصور والتعليمات و`response_json_schema`.
2. اجمع `chunk.text` في raw buffer.
3. مرر chunks إلى JSON parser تدريجي يحتمل القطع داخل كلمة عربية أو Unicode escape أو وسم HTML.
4. عند اكتمال عنصر داخل `pages`، طبّق Pydantic validation وفحص `pdf_page` وعدم التكرار.
5. خزّن العنصر في staging مرتبطًا بـ`request_id` وأرسل حدث UI مثل `page_received`.
6. اجمع آخر `finish_reason` و`usage_metadata` غير فارغين.
7. عند `STOP`، تحقق من JSON الكامل ومجموعة الصفحات ثم انقل staging إلى الصفحات في transaction واحدة.
8. عند انقطاع أو `MAX_TOKENS` أو JSON ناقص، علّم الطلب `partial` وصغر الدفعة تلقائيًا.

لا تستخدم `split` على الأقواس أو الفواصل. قيّم `ijson` incremental coroutine أو state machine محدودة للـschema الحالي، واختر بعد اختبار المكتبة وحجمها وترخيصها.

في الإصدار الأول، تظل الصفحات في staging حتى نجاح التحقق النهائي، ثم تعتمد. هذا يمنع حفظ نتائج من stream غير مكتمل. تحسين لاحق، بعد اختبارات مستقلة، يمكنه اعتماد عناصر مكتملة من طلب انتهى بـ`MAX_TOKENS` وإعادة الصفحات الناقصة فقط.

### 7. التكيف مع النجاح والفشل

- `MAX_TOKENS`: اقسم الدفعة إلى نصفين وأعدها.
- payload أكبر من السياسة: صغرها قبل الإرسال.
- 504 أو انقطاع متكرر: صغر الدفعة وزد timeout ضمن سقف.
- صفحة ناقصة أو مكررة أو غير مطلوبة: لا تعتمد الدفعة، ثم أعدها أصغر.
- عدة نجاحات متتالية مع هامش إدخال وإخراج جيد: ارفع الهدف خطوة.
- 401 أو 403: أوقف المهمة برسالة مفتاح أو صلاحية.
- 404 لموديل: حدّث catalog واطلب اختيار موديل متاح.
- 429 أو 503: انتظر وأعد المحاولة وفق backoff من دون اعتبار الصفحات فاشلة فورًا.
- إلغاء المستخدم: أغلق stream، امسح staging للطلب غير المكتمل، واترك الطلبات المعتمدة السابقة سليمة.

## تغييرات الملفات المتوقعة

### `waraq/gemini_client.py`

- فصل سجل توافق OCR عن الأسعار والحصص.
- إرجاع `ModelCapabilities` من `models.list/get`.
- إضافة `count_tokens` لطلب دفعة حقيقي.
- جعل `max_output_tokens` مدخلًا محسوبًا.
- إضافة `extract_pages_stream` وأحداث chunks/صفحات.
- تصنيف الأخطاء إلى rate limit، auth، model unavailable، output limit، transport، timeout، malformed output.

### `waraq/database.py`

- migrations لملفات حصة المشروع وربط المفاتيح بها.
- cache لقدرات الموديلات.
- تخزين إعداد auto/fixed وحد المستخدم.
- إضافة حقول الطلب: الصفحات المخططة، الإدخال المحجوز والفعلي، الإخراج المتوقع والفعلي، حد الموديل وقت الطلب، finish reason، parent request، وحالة `partial`.
- جدول staging لصفحات stream.
- ledger ذري لـRPM وinput TPM وRPD على مستوى المشروع والموديل.

### `waraq/tasks.py`

- استبدال التقسيم المسبق الثابت باستدعاء `BatchPlanner` قبل كل دفعة.
- بث حالات `planning`, `waiting_quota`, `sending`, `receiving`, `page_received`, `committing`, `retrying`.
- backoff والتقسيم التلقائي وسياسة الإيقاف والاستئناف.
- عدم وسم كل صفحات الدفعة failed عند أول خطأ مؤقت.

### `waraq/bridge.py`

- واجهات استيراد CSV وربط المفتاح بملف حصة.
- إتاحة قدرات الموديل ومصدرها وقدمها للواجهة.
- إعداد `batch_mode=auto|fixed` و`max_pages_per_request`.
- عرض سبب اختيار planner لحجم الدفعة من دون كشف بيانات حساسة.

### `waraq/qml/Main.qml`

- جعل «تلقائي» الافتراضي لعدد الصفحات في الطلب.
- إبقاء حد يدوي متقدم بدل قيمة إجبارية.
- حذف النص الذي يدعي «صفحة في كل استعلام» أو أي عدد ثابت.
- عرض الحصة باعتبارها حصة مشروع، لا حصة مفتاح.
- عرض الموديل، عدد صفحات الدفعة، التقدم المستلم والمؤكد، وسبب الانتظار أو تصغير الدفعة.
- إضافة واجهة استيراد CSV مع preview وتحذير قدم البيانات.

### الاختبارات

- وسع `tests_desktop/test_gemini.py` لاختبار metadata والعد والاستريمنج والحدود المختلفة.
- وسع `tests_desktop/test_library.py` لاختبار migrations وملف الحصة المشترك والـledger وstaging والاستئناف.
- وسع `tests_desktop/test_qml_visual_contract.py` لاختبار الوضع التلقائي وتسميات حصة المشروع وتقدم stream.
- أضف وحدة اختبارات مستقلة لـ`BatchPlanner` إن وضع في ملف جديد مثل `waraq/batching.py`.

## ترتيب التنفيذ

### المرحلة 1: فصل البيانات والحدود

1. أضف الاختبارات لنموذجي `ModelCapabilities` و`ProjectQuotaProfile`.
2. أضف migrations مع ترحيل آمن للبيانات الحالية.
3. افصل سجل توافق OCR عن `MODEL_DAILY_LIMITS` و`DEFAULT_QUOTAS`.
4. أضف adapter لـ`models.list/get` وcache.
5. أضف مستورد CSV وpreview وربط المفاتيح بملف حصة.

معيار القبول: موديل وهمي حد إخراجه 8,192 يغير البيانات من دون تعديل أي ثابت، ومفتاحان في ملف حصة واحد يشتركان في الاستهلاك.

### المرحلة 2: المخطط والـledger

1. أنشئ `waraq/batching.py` بأنواع قرار واضحة وقابلة للاختبار.
2. أضف قيود input/output/TPM/payload/حد المستخدم.
3. أضف `count_tokens` والحجز الذري.
4. سجل سبب توقف زيادة الدفعة في الطلب.
5. حافظ على fixed mode للمهام القديمة.

معيار القبول: لا ينتج planner دفعة تتجاوز أي حد في اختبارات boundary، ويظل القرار قابلًا لإعادة البناء من سجل الطلب.

### المرحلة 3: الاستريمنج وstaging

1. اكتب اختبارات chunks قبل التنفيذ، مع قطع JSON في مواضع تعسفية.
2. أضف parser تدريجي و`extract_pages_stream`.
3. أضف staging وcommit النهائي.
4. أضف تقسيمًا تلقائيًا للدفعة وسياسات retry.

معيار القبول: stream مقطع داخل نص عربي وescape وHTML ينتج كل صفحة مرة واحدة، ولا تعتمد أي صفحة من stream غير صالح.

### المرحلة 4: الواجهة

1. اجعل auto افتراضيًا للمهام الجديدة.
2. اعرض حدود الموديل وحصة المشروع كمفهومين منفصلين.
3. اعرض تقدم الاستلام لحظة بلحظة من دون عرض JSON الخام.
4. أضف استيراد CSV وربط ملف الحصة بالمفاتيح.
5. حدّث نصوص الدفعة وأزل الادعاءات القديمة.

معيار القبول: يرى المستخدم لماذا اختير حجم الدفعة، ويرى الصفحات تصل أثناء الطلب الطويل، ويمكنه الإيقاف والاستكمال من آخر دفعة معتمدة.

### المرحلة 5: قياس حي محدود

بعد نجاح الاختبارات المحلية، نفذ smoke test اختياريًا بمفتاح المستخدم لكل موديل متاح. اختبر 4 ثم 8 ثم 16 ثم 24 ثم 32 صفحة من كتاب مطبوع ومن مخطوط، وسجل:

- زمن أول chunk والزمن الكلي.
- prompt، candidate وthinking tokens.
- نسبة الإخراج إلى السقف.
- الصفحات الناقصة أو المكررة.
- 429 و503 و504 و`MAX_TOKENS`.
- دقة النص وترتيب الصفحات مقارنة بخط أساس الصفحة المفردة.

لا تجعل الاختبارات الحية جزءًا من test suite الافتراضي، ولا تستخدمها من دون مفتاح يقدمه المستخدم صراحة.

## حالات الاختبار الإلزامية

- تحليل `530 / 250K`, `1.06K / 250K`, `0 / 0` والقيم الفارغة.
- تجاهل صفوف grounding وLive API وTTS وتوليد الصور.
- مطابقة `Gemini 3 Flash` مع `gemini-3-flash-preview` دون تخمين.
- metadata حديث وقديم ومفقود وفشل شبكة.
- موديلات بحدود إخراج مختلفة، ومنها 8,192 و65,536 في fixtures.
- موديل يدعم `generateContent` لكنه غير معتمد للصور أو Structured Outputs.
- مفتاحان في مشروع واحد ومفتاحان في مشروعين مختلفين.
- مهمتان متزامنتان تتنافسان على RPM وTPM.
- تجاوز input limit وTPM وpayload وoutput estimate كل على حدة.
- chunks فارغة، قطع داخل UTF-8 escape وHTML، وmetadata لا يظهر إلا في النهاية.
- `STOP`, `MAX_TOKENS`, 429, 503, 504، انقطاع stream وإلغاء المستخدم.
- تكرار `pdf_page` ورقم غير مطلوب وصفحة ناقصة.
- مهمة قديمة fixed ومهمة جديدة auto.
- عدم كشف API key في الخطأ أو السجل أو أحداث UI.

## بوابة الإنجاز

لا تعد الميزة مكتملة إلا إذا تحقق الآتي:

- لا توجد حصة موديل ثابتة داخل catalog المستخدم لاختيار الدفعة.
- كل طلب يسجل نسخة metadata والحدود التي بُني عليها.
- `max_output_tokens` مشتق من الموديل والتقدير، لا من ثابت عام.
- planner يحترم input limit وoutput limit وinput TPM وRPM وRPD وpayload.
- مفاتيح المشروع نفسه تشترك في quota ledger.
- الدفعة الطويلة تعرض تقدمًا حقيقيًا عبر stream.
- الأخطاء المؤقتة لا تحول كل الصفحات فورًا إلى failed.
- الإيقاف والاستئناف لا يعيدان الصفحات المعتمدة.
- الاختبارات المحلية تمر، ثم ينجح smoke test بموديلين على الأقل لهما ملفا حصة مختلفان أو fixtures بحدود مختلفة.
- النصوص العربية لا تدعي أن كل طلب يعالج صفحة واحدة أو أن أرقام CSV هي حدود الطلب.

## ما هو خارج النطاق

- scraping لصفحة AI Studio.
- OAuth وCloud Quotas API في الإصدار الأول.
- Batch API غير المتزامن، لأن المطلوب تقدم حي.
- دعم موديلات الصوت والصورة وLive API في مسار OCR.
- اعتبار تبديل API key طريقة لمضاعفة حصة المشروع.
- اعتماد صفحات stream غير المكتمل قبل إنجاز اختبارات salvage مستقلة.

## المصادر الرسمية

- [Models API](https://ai.google.dev/api/models)
- [فهم وعد التوكنات](https://ai.google.dev/gemini-api/docs/tokens)
- [Counting tokens API](https://ai.google.dev/api/tokens)
- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [GenerateContent وstreamGenerateContent](https://ai.google.dev/api/generate-content)
- [Structured Outputs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)
- [Image understanding](https://ai.google.dev/gemini-api/docs/image-understanding)
- [File input methods](https://ai.google.dev/gemini-api/docs/file-input-methods)
- [Troubleshooting and retries](https://ai.google.dev/gemini-api/docs/troubleshooting)
- [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/)

## مراجع المشروع

- `docs/research/gemini-dynamic-model-limits.md`
- `docs/research/gemini-large-batches-and-streaming.md`
- `docs/research/gemini-api-rate-limits.md`
- `docs/research/gemini-caching-and-multipage-requests.md`

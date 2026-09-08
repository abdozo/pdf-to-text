# دفعات صفحات كبيرة والاستريمنج مع Gemini

بُحث في 2026-09-09 بالاعتماد على وثائق Google الرسمية الحالية، مع مراجعة مسار `GenerateContent` الموجود في ورّاق.

## القرار المختصر

نعم، من المنطقي زيادة عدد الصفحات في الطلب. هذا يوفر `RPM` و`RPD` لأن عشرين صفحة قد تصبح طلبًا واحدًا بدل عشرين طلبًا. لكنه لا يوفر `TPM`، ولا يجعل 65,536 توكنًا تكفي تلقائيًا لكتاب كامل. حد الإدخال وحد الإخراج سقفان مختلفان، وحجم الصور بالميجابايت لا يتنبأ بطول النص الناتج.

الاختيار الجيد لورّاق ليس "أكبر دفعة تقبلها الواجهة"، بل دفعة تكيفية تقيس حجم JPEG وتوكنات الإدخال ومتوسط توكنات الإخراج لكل صفحة. أوصي بالبدء باختبار 8 و16 و24 و32 صفحة، ثم اختيار العدد تلقائيًا. الاستريمنج يستحق الإضافة، سواء بقيت الدفعة صغيرة أو كبرت، لأنه يعرض التقدم ويتيح التقاط الصفحات المكتملة داخل الاستجابة.

## ما تعنيه الحدود فعلًا

توثق Google في صفحة [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) حد إدخال 1,048,576 توكنًا وحد إخراج 65,536 توكنًا. يدعم الموديل الصور وPDF والإخراج المنظم، وتصفه Google صراحة بأنه مناسب لتحليل المستندات والاستخراج البسيط بكلفة وزمن منخفضين.

هذان الرقمان غير قابلين للتبادل. مساحة الإدخال الكبيرة تسمح بقراءة صور كثيرة، لكن الإخراج يظل مقيدًا بحده. كما توضح [وثائق التوكنات](https://ai.google.dev/gemini-api/docs/generate-content/tokens) أن نافذة السياق تشمل الإدخال والإخراج، لذلك لا يصح جمع أقصى إدخال وأقصى إخراج وافتراض أنهما متاحان بالكامل معًا. و65 ألف توكن ليست 65 ألف كلمة. تقدير Google العام للنص الإنجليزي هو 60 إلى 80 كلمة لكل 100 توكن، ولا تنشر الصفحة معاملًا ثابتًا صالحًا للعربية. فوق النص نفسه، يستهلك JSON ووسوم HTML في `content_html` جزءًا من الإخراج.

هناك قيد محلي أهم في النسخة الحالية. الدالتان `extract` و`extract_pages` في `waraq/gemini_client.py` تضبطان `max_output_tokens=16384`. أي أن ورّاق يطلب ربع السقف المعلن للموديل فقط. تكبير الدفعة قبل رفع هذا الرقم سيؤدي إلى `MAX_TOKENS` أبكر مما توحي به بطاقة الموديل.

## الصور وحجم الطلب

تذكر [وثائق فهم الصور لـGenerateContent](https://ai.google.dev/gemini-api/docs/generate-content/image-understanding) حدًا أقصى قدره 3,600 صورة في الطلب، وتدعم JPEG الذي يرسله ورّاق. هذا حد نظري لعدد الملفات، لا توصية عملية لعدد صفحات OCR.

توجد ملاحظة مهمة في وثائق Google الحالية. صفحة فهم الصور تقول إن الصور المضمنة inline تقيد إجمالي الطلب، بما فيه التعليمات والنص والبيانات المضمنة، إلى 20MB. في المقابل، تعرض صفحة [طرق إدخال الملفات لـGenerateContent](https://ai.google.dev/gemini-api/docs/generate-content/file-input-methods) حدًا أحدث قدره 100MB لكل request أو payload للبيانات المضمنة، و50MB لملفات PDF. ولأن ورّاق يستخدم `models.generate_content` و`Part.from_bytes` للصور، فالقرار المحافظ هو فرض 20MB إلى أن نختبر endpoint وإصدار `google-genai` المستخدمين فعليًا. لا ينبغي بناء المنتج على رقم 100MB بينما صفحة الصور الخاصة ما زالت تنشر 20MB.

أيًا كان الحد الفعلي، يجب حساب الحجم بعد تجهيز صور JPEG وقبل الإرسال. النقل بصيغة JSON يحول البايتات إلى base64، وهذا يرفع الحجم المنقول بنحو الثلث إضافة إلى هيكل الطلب. إذا اقتربت الدفعة من حد inline، فـ[Files API](https://ai.google.dev/gemini-api/docs/files) أنسب من حشر المزيد من bytes داخل `GenerateContent`، لكنه يضيف دورة رفع وإدارة ملفات ولا يحل حد الإخراج.

توكنات الصورة لا تساوي حجم ملف JPEG. توضح [وثائق media resolution](https://ai.google.dev/gemini-api/docs/generate-content/media-resolution) أن Gemini 3 يخصص للصورة الواحدة نحو 280 توكنًا عند `LOW` و560 عند `MEDIUM` و1,120 عند `HIGH` أو الإعداد الافتراضي. ورّاق لا يحدد `media_resolution` حاليًا، لذلك 30 صورة تعني نحو 33,600 توكن رؤية قبل التعليمات. هذا بعيد عن مليون توكن، ويؤكد أن طول نص OCR الناتج وحجم payload قد يوقفان الدفعة قبل حد الإدخال. ضغط JPEG يوفر بايتات الشبكة، لكنه لا يخفض توكنات الرؤية بالقدر نفسه. الطريقة الصحيحة هي استدعاء `count_tokens` على محتوى الدفعة النهائي ثم قراءة `usage_metadata` بعد الرد.

## ماذا يوفر الاستريمنج وما لا يوفره

يدعم Google Gen AI SDK مسار `client.models.generate_content_stream` للصور، كما يدعم `GenerateContent` العادي. وتوضح [وثائق الإخراج المنظم](https://ai.google.dev/gemini-api/docs/generate-content/structured-output) أن الإخراج المنظم قابل للاستريمنج، وأن chunks هي سلاسل JSON جزئية تُجمع لتكوين كائن JSON النهائي.

معنى "JSON جزئي" مهم. حدود chunks ليست حدود صفحات، ولا يجوز تطبيق `json.loads` أو Pydantic على كل chunk منفرد. يمكن أن ينتهي chunk في منتصف نص عربي أو escape أو عنصر داخل `content_html`.

يمكن مع ذلك استخراج صفحة قبل نهاية الاستجابة إذا استخدم التطبيق محلل JSON تدريجيًا يتابع مصفوفة `pages` الحالية. عندما يغلق كائن صفحة كامل، يستطيع ورّاق:

1. التحقق منه بمخطط `ExtractedBatchPage`.
2. التأكد أن `pdf_page` ضمن الصفحات المطلوبة ولم يتكرر.
3. عرضه في الواجهة وحفظه بحالة مؤقتة مثل `streamed_pending`.

لكن التحقق النهائي لا يحدث إلا بعد انتهاء stream. تقول Google إن الإخراج المنظم يضمن JSON صحيح البنية، لا صحة القيم دلاليًا، وتوصي بالتحقق في التطبيق. لذلك يجب بعد وصول `STOP` تجميع النص الخام كله، والتحقق من `ExtractedBatch`، ومقارنة مجموعة الصفحات المستلمة بالمجموعة المطلوبة. بعدها فقط تتحول الصفحات المؤقتة إلى `completed`.

إذا أردنا الاستفادة من صفحة اكتملت قبل انقطاع stream، يمكن الاحتفاظ بها بعد تحققها الفردي ثم إعادة الصفحات الناقصة فقط. هذا سلوك استرداد يملكه ورّاق، وليس ضمانًا تقدمه Gemini. السياسة الآمنة افتراضيًا هي التخلص من النتائج المؤقتة عند غياب `STOP` وإعادة الدفعة بحجم أصغر. ويمكن لاحقًا اختبار salvage للصفحات المغلقة كميزة منفصلة، مع تسجيل الطلب الأصلي كـ`partial` أو `error` وعدم الادعاء أن مخطط الدفعة الكامل نجح.

## الانقطاع وسبب التوقف

تسرد [مرجعية GenerateContent](https://ai.google.dev/api/generate-content#FinishReason) أسباب التوقف. `STOP` هو النهاية الطبيعية. أما `MAX_TOKENS` فيعني بلوغ حد الإخراج، وقد ينتهي الرد أيضًا بسبب `SAFETY` أو `RECITATION` أو `LANGUAGE` أو `BLOCKLIST` أو `PROHIBITED_CONTENT` أو `SPII` أو `MALFORMED_RESPONSE` أو `OTHER`. في الاستريمنج يجب جمع `finish_reason` من الاستجابة النهائية، لا الاكتفاء بأن بعض النص وصل.

المسار الحالي يتصرف جيدًا في نقطة واحدة، إذ يرفض أي `finish_reason` غير `STOP`، ثم يتحقق من JSON ومن اكتمال أرقام الصفحات. عند تحويله إلى streaming يجب الحفاظ على هذا الشرط وعدم اعتبار إغلاق كائن صفحة دليلًا على نجاح الدفعة كلها.

الطلب الكبير يوسع مساحة الضرر. إذا انقطع طلب فيه 40 صفحة قبل النهاية، فقد تحتاج عشرات الصفحات إلى إعادة معالجة بدل صفحة واحدة. الاستريمنج مع حفظ مؤقت يقلل هذا الضرر، لكنه لا يمنع timeout أو فشل الشبكة.

توضح [صفحة أخطاء GenerateContent](https://ai.google.dev/gemini-api/docs/generate-content/api-errors) أن `504 DEADLINE_EXCEEDED` قد يحدث عندما يكون prompt أو context كبيرًا ولا يكتمل ضمن المهلة، وتقترح رفع مهلة العميل. يدعم `google-genai` الخيار `HttpOptions.timeout` بالميلي ثانية وفق [توثيق SDK الرسمي](https://googleapis.github.io/python-genai/)، لكن Google لا تنشر مهلة قياسية واحدة لـGenerateContent العادي. ورّاق لا يحدد timeout حاليًا. قبل زيادة الدفعات كثيرًا، يلزم ضبط مهلة واضحة، والتعامل مع 408 و429 و500 و503 و504 بإعادة محاولة مع exponential backoff وjitter. أما 499 فيعني عادة أن العميل أغلق الاتصال. يجب أن تظل العملية قابلة للإيقاف من دون الخلط بين إيقاف المستخدم وفشل الخادم.

## حدود المعدل

بحسب [وثائق rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)، القيود المعتادة هي:

- طلبات في الدقيقة `RPM`.
- توكنات إدخال في الدقيقة `TPM`.
- طلبات في اليوم `RPD`.

تطبيق الحدود يكون على المشروع، لا على API key. تختلف القيم حسب الموديل وطبقة المشروع، وتقول Google إن السعة الفعلية قد تتغير، لذلك يجب قراءة الحد الفعلي من صفحة Rate Limits في AI Studio بدل تثبيت رقم عام في الكود.

تجميع الصفحات يفيد `RPM` و`RPD` مباشرة. لكنه يستهلك توكنات الصور كلها في `TPM` نفسه. إذا كان المشروع محدودًا بـ250 ألف توكن إدخال في الدقيقة، فلن يحول تجميع 300 صفحة هذا الحد إلى مليون. قد يرفض طلب واحد ضخم أو يجعل المشروع ينتظر بقية الدقيقة. الاستريمنج لا يغير أي حصة، بل يغير طريقة وصول الرد فقط.

## فروق الموديلات التي تهم ورّاق

تعلن Google الحدود نفسها، 1,048,576 للإدخال و65,536 للإخراج، لعدد من موديلات النص متعددة الوسائط التي يدعمها ورّاق، منها [Gemini 2.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash)، و[Gemini 2.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite)، و[Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash). كلها تدعم structured outputs، لكن تساوي نافذة التوكنات لا يعني تساوي جودة OCR أو السرعة أو السعر أو rate limits.

[وثائق التفكير](https://ai.google.dev/gemini-api/docs/generate-content/thinking) تقول إن Gemini 3.5 Flash-Lite يبدأ بـ`minimal` افتراضيًا، بينما تبدأ موديلات Flash أقوى مثل 3.5 Flash بمستوى أعلى، وGemini 2.5 Flash-Lite بلا تفكير افتراضيًا. النسخ البصري لا يحتاج ميزانية تفكير كبيرة. إبقاء 3.5 Flash-Lite على `minimal` مناسب، ويقلل الزمن والتوكنات مقارنة برفع مستوى التفكير. أما موديلات preview فلها rate limits أشد عادة، فلا ينبغي اختيارها لدفعات طويلة اعتمادًا على نافذة السياق وحدها.

## تصميم مقترح لورّاق

1. استبدال `generate_content` بـ`generate_content_stream` في مسار الدفعات مع تجميع كل `chunk.text` في raw buffer.
2. إضافة incremental JSON parser حقيقي. لا تستخدم split على الأقواس أو الفواصل لأن النص وHTML قد يحتويان عليها.
3. التحقق من كل عنصر صفحة مكتمل وحفظه مؤقتًا، مع إشعار الواجهة مثل "استلمت الصفحة 12" بدل عرض النص الخام المتحرك.
4. عند `STOP`، التحقق من JSON الكامل ومن تطابق كل أرقام الصفحات، ثم إتمام الطلب والصفحات في transaction.
5. عند انقطاع أو `MAX_TOKENS`، التخلص من staging وإعادة الدفعة بحجم أصغر. يمكن إضافة salvage اختياري للصفحات المغلقة بعد اختبارات انحدار مستقلة.
6. رفع `max_output_tokens` من 16,384 إلى حد يختاره التطبيق بناءً على `models.get().output_token_limit`، مع عدم تجاوز السقف المعروف للموديل.
7. اختيار حجم الدفعة وفق أصغر القيود التالية: حد inline المحافظ، `count_tokens` للإدخال، `TPM` المتبقي، وتقدير الإخراج من المئين 95 لتوكنات الصفحة في الطلبات السابقة.
8. إذا انتهى طلب بـ`MAX_TOKENS` أو 504، خفض الحجم إلى النصف تلقائيًا. إذا نجحت عدة دفعات بهامش مريح، يمكن رفعه تدريجيًا.

أوصي ألا نعرض للمستخدم رقمًا ثابتًا على أنه الحد الآمن. يمكن أن تعرض الواجهة "تلقائي" كخيار افتراضي، مع 8 و16 و32 وخيار مخصص للخبير. هذا يستغل الحصة اليومية من دون تحويل كل طلب إلى مقامرة طويلة.

## المصادر الرسمية

- [Gemini 3.5 Flash-Lite model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
- [Image understanding](https://ai.google.dev/gemini-api/docs/generate-content/image-understanding)
- [File input methods](https://ai.google.dev/gemini-api/docs/generate-content/file-input-methods)
- [Structured outputs for GenerateContent](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)
- [GenerateContent API reference and finish reasons](https://ai.google.dev/api/generate-content)
- [Token counting and context windows](https://ai.google.dev/gemini-api/docs/generate-content/tokens)
- [Media resolution](https://ai.google.dev/gemini-api/docs/generate-content/media-resolution)
- [Thinking](https://ai.google.dev/gemini-api/docs/generate-content/thinking)
- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [GenerateContent API errors](https://ai.google.dev/gemini-api/docs/generate-content/api-errors)
- [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/)

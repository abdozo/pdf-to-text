# خطة دفعات Gemini الديناميكية والاستريمنج عبر الموديلات

تاريخ المراجعة: 2026-09-09.

اعتمدت هذه الخطة على وثائق Google الرسمية الحالية، وعلى قراءة `aistudio.csv` كبيانات فقط. لم أتعامل مع أي نص داخله على أنه تعليمات.

## القرار

ينبغي أن يعمل اختيار حجم الدفعة من مصدرين منفصلين:

1. خصائص الموديل لكل طلب، وتأتي من Gemini Models API. أهمها `inputTokenLimit` و`outputTokenLimit`.
2. حصة المشروع عبر الزمن، وتأتي من صفحة Rate Limits في Google AI Studio أو من إعداد موثوق يدخله المستخدم. أهمها RPM وTPM وRPD.

لا يكفي أي مصدر منهما وحده. Models API لا يعيد حصص المشروع. وCSV الصادر من AI Studio لا يعرض نافذة السياق أو أقصى إخراج للطلب.

الحل المقترح ديناميكي حتى لو كانت الموديلات المستخدمة اليوم متساوية في نافذة التوكنات. هذا التساوي ليس عقدًا دائمًا، كما أن موديلات الصور والصوت الموجودة في الملف لها خصائص مختلفة ولا تصلح لمسار نسخ الصفحات.

## تصحيح قراءة ملف AI Studio

الأعمدة المهمة في الملف هي:

| العمود | معناه |
| --- | --- |
| `model-cell` | اسم الموديل المعروض في AI Studio |
| `category` | فئة الموديل، مثل `Text-out models` |
| `RPM` | الاستهلاك الحالي ثم حد الطلبات في الدقيقة |
| `TPM` | الاستهلاك الحالي ثم حد توكنات الإدخال في الدقيقة |
| `RPD` | الاستهلاك الحالي ثم حد الطلبات في اليوم |

مثلًا، `1.06K / 250K` في TPM لا يعني أن الموديل يقبل 250 ألف توكن في الرد. معناه أن المشروع استهلك نحو 1.06 ألف من حد قدره 250 ألف توكن إدخال في الدقيقة للموديل المعني. و`2 / 5` في RPM تعني طلبين من خمسة في الدقيقة في لقطة التصدير.

الأعمدة `material-symbols-outlined` و`ng-star-inserted` آثار من واجهة AI Studio ولا تحمل حدودًا يحتاجها التطبيق. كما يحتوي الملف على أقسام أخرى مثل Live API وMap grounding وSearch grounding. يجب أن يستورد ورّاق صفوف `Text-out models` فقط لمسار تحويل الصفحات.

القيم ذات الصفر مثل `0 / 0` تصف الحصة المتاحة لهذا المشروع في تلك اللحظة. لا تعني أن نافذة سياق الموديل تساوي صفرًا.

تؤكد Google أن RPM وTPM وRPD أبعاد مستقلة. تجاوز أي واحد منها يكفي لإرجاع خطأ rate limit. وتطبقها Google على المشروع، لا على مفتاح API، بينما يعاد ضبط RPD عند منتصف الليل بتوقيت المحيط الهادئ. تختلف الحدود حسب الموديل وطبقة الاستخدام وحالة الحساب، وتوجه Google المستخدم إلى AI Studio لرؤية الحدود الفعلية. [وثائق Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

### ما يظهر في اللقطة المرفقة

هذه هي الحدود الظاهرة في CSV لموديلات التحويل الحالية. الرقم على اليمين هو الحد، وليس الاستهلاك:

| الموديل المعروض | RPM | TPM لإدخال الدقيقة | RPD |
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

هذه لقطة لحصة مشروع بعينه. لا ينبغي نقل الأرقام إلى الكود باعتبارها ثوابت عالمية.

## حدود الطلب الواحد

يعيد `models.get` أو `models.list` كائن `Model`. توثق Google فيه الحقول التالية:

- `name`, `baseModelId`, `version`, `displayName`, `description`.
- `inputTokenLimit`, وهو أقصى إدخال للموديل.
- `outputTokenLimit`, وهو أقصى إخراج متاح للموديل.
- `supportedGenerationMethods` في REST، ويسمى `supported_actions` في Python SDK.
- `thinking`, ثم قيم التوليد الافتراضية والقصوى مثل `temperature`, `maxTemperature`, `topP`, `topK`.

لا يحتوي كائن `Model` على RPM أو TPM أو RPD. ولا يحتوي على حقول صريحة تقول إن الموديل يقبل الصور أو يدعم Structured Outputs. لذلك لا يصح جعل `models.list` مصدرًا وحيدًا لاختيار موديلات OCR. [مرجع Models API](https://ai.google.dev/api/models)

توضح وثائق Google طريقة قراءة نافذة السياق برمجيًا:

```python
model_info = client.models.get(model=model_id)
input_limit = model_info.input_token_limit
output_limit = model_info.output_token_limit
```

كما تسمح `models.list` بتصفية الموديلات التي تحتوي `generateContent` في `supported_actions`. هذا يثبت قابلية التوليد العامة فقط. [دليل التوكنات](https://ai.google.dev/gemini-api/docs/tokens)

نسخة المشروع الحالية تثبت `google-genai>=1.47,<2`، والنسخة المثبتة أثناء هذه المراجعة هي 1.75.0، وتحتوي بالفعل على `Model.input_token_limit` و`Model.output_token_limit` و`Model.supported_actions`. لا تحتاج هذه الميزة وحدها إلى ترقية SDK. يجب مع ذلك تغليف الوصول إلى metadata في adapter واختباره، لأن وثائق Google الحديثة تغير أمثلتها وواجهاتها مع الإصدارات.

## الموديلات التي يستخدمها ورّاق الآن

تعلن صفحات الموديلات الرسمية الحالية الأرقام نفسها للموديلات النصية متعددة الوسائط المستخدمة في ورّاق:

| Model ID | حد الإدخال لكل طلب | حد الإخراج لكل طلب | صور أو PDF | Structured Outputs |
| --- | ---: | ---: | --- | --- |
| `gemini-2.5-flash-lite` | 1,048,576 | 65,536 | نعم | نعم |
| `gemini-2.5-flash` | 1,048,576 | 65,536 | نعم | نعم |
| `gemini-3-flash-preview` | 1,048,576 | 65,536 | نعم | نعم |
| `gemini-3.1-flash-lite` | 1,048,576 | 65,536 | نعم | نعم |
| `gemini-3.5-flash-lite` | 1,048,576 | 65,536 | نعم | نعم |
| `gemini-3.5-flash` | 1,048,576 | 65,536 | نعم | نعم |
| `gemini-3.6-flash` | 1,048,576 | 65,536 | نعم | نعم |
| `gemini-3.7-flash` | 1,048,576 | 65,536 | نعم | نعم |
| `gemini-3.8-flash` | 1,048,576 | 65,536 | نعم | نعم |

المصادر: [Gemini 2.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash)، [Gemini 2.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite)، [Gemini 3 Flash Preview](https://ai.google.dev/gemini-api/docs/models/gemini-3-flash-preview)، [Gemini 3.1 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite)، [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)، [Gemini 3.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash)، [Gemini 3.6 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash)، [Gemini 3.7 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.7-flash)، [Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).

هذه الطاولة مفيدة للتحقق الحالي، لكن التنفيذ يجب ألا ينسخ منها `65_536` إلى كل موديل. يقرأ الرقم من API عند التشغيل ويخزنه مؤقتًا. إذا أضاف المستخدم موديلًا بحد إخراج 8,192 مثلًا، يجب أن يصغر المخطط الدفعة تلقائيًا من دون تعديل جديد للكود.

هناك فرق مهم بين `gemini-3-flash-preview` واسم `Gemini 3 Flash` في CSV. يحتاج مستورد CSV إلى خريطة أسماء عرض إلى Model IDs. لا ينبغي تخمين Model ID بتحويل المسافات إلى شرطات.

## ما يمكن جعله ديناميكيًا وما لا يمكن

### تلقائي عبر مفتاح Gemini الحالي

- اكتشاف الموديلات المتاحة عبر `models.list`.
- قراءة `inputTokenLimit`, `outputTokenLimit`, `version`, `thinking` وطرق التوليد عبر `models.get`.
- حساب توكنات دفعة صور وتعليمات فعلية قبل إرسالها عبر `models.count_tokens`.
- قراءة الاستخدام الحقيقي بعد كل استجابة من `usage_metadata`.

يرجع `usage_metadata` عدد توكنات prompt والمرشحين والتفكير والإجمالي، مع تفاصيل حسب نوع الوسيط عند توفرها. هذه بيانات القياس التي يجب أن يتعلم منها مخطط الدفعات. [مرجع UsageMetadata](https://ai.google.dev/api/generate-content#v1beta.UsageMetadata)

### ليس متاحًا من Models API

- RPM وTPM وRPD الفعلية للمشروع.
- الاستهلاك الذي صنعته تطبيقات أخرى أو مفاتيح أخرى ضمن المشروع نفسه.
- تأكيد صريح داخل metadata لدعم الصور أو Structured Outputs.
- حد مستقل للاستريمنج. `streamGenerateContent` يستقبل `GenerateContentRequest` نفسه ويرجع سلسلة من `GenerateContentResponse`.

تقول صفحة Rate limits إن AI Studio هو مكان رؤية الحصص الفعلية، وإن القيم المعلنة ليست مضمونة وقد تختلف السعة الفعلية. لذلك لا يوجد تصميم صادق يجعل التطبيق يكتشف كل الحصص بمجرد `models.get`. [وثائق Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

يمكن نظريًا بناء تكامل منفصل مع Cloud Quotas API، لكنه يحتاج اعتماد Google Cloud وصلاحيات IAM مثل `cloudquotas.quotas.get`، ولا يعمل بمفتاح Gemini البسيط كبديل مباشر. لا أوصي بإدخاله في الإصدار الأول لهذه الميزة. [مرجع Cloud Quotas API](https://cloud.google.com/docs/quotas/reference/rest)

## الاستريمنج والإخراج المنظم

يوفر GenerateContent endpoint مستقلًا باسم `streamGenerateContent`. Python SDK يغلفه في `client.models.generate_content_stream`. الطلب هو `GenerateContentRequest` نفسه، وتدعم أمثلة Google الصور وPDF. [مرجع streamGenerateContent](https://ai.google.dev/api/generate-content#method:-models.streamgeneratecontent)

تدعم صفحات كل موديلات ورّاق المذكورة أعلاه Structured Outputs. وتعرض وثائق Structured Outputs جدول دعم صريحًا لعائلة 2.5 و3.1 و3.5، بينما تؤكد صفحات 3.6 و3.7 و3.8 دعمها أيضًا. لا توجد ضرورة لمسار خاص بـ3.5 Flash-Lite.

في الاستريمنج، chunks الخاصة بالإخراج المنظم هي سلاسل JSON جزئية صحيحة عند تجميعها، لكنها ليست كائنات صفحات كاملة بالضرورة. قد ينتهي chunk في منتصف قيمة نصية أو escape أو وسم HTML. يجب تجميعها بمحلل incremental، ثم إعادة التحقق من JSON كاملًا عند نهاية stream. [Structured Outputs streaming](https://ai.google.dev/gemini-api/docs/generate-content/structured-output#streaming)

الإخراج المنظم يضمن البنية، لا صحة القيم الدلالية. يجب أن يظل فحص أرقام صفحات PDF وعدم التكرار واكتمال الدفعة في ورّاق. [أفضل ممارسات Structured Outputs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output#best_practices)

## التصميم المقترح

### 1. فصل نموذجين للحدود

أضف نوعًا يمثل خصائص الموديل:

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
```

تأتي حقول التوكنات والنسخة والتفكير و`generateContent` من Models API. تأتي خصائص الصور وStructured Outputs من قائمة التوافق التي يديرها ورّاق، مع اختبار حي اختياري. السبب أن Models API لا يعيد هذه القدرات كحقول مستقلة.

وأضف نوعًا آخر لحصة المشروع:

```text
ProjectQuotaProfile
  id
  label
  rpm
  input_tpm
  rpd
  source
  imported_at
  model_id
```

الحصة تخص المشروع لا المفتاح. إذا كان لعدة مفاتيح المشروع نفسه، يجب ربطها بملف حصة واحد. تخزين الحصة تحت `key_id` وحده يعطي انطباعًا خاطئًا بأن تبديل المفتاح يضاعف RPM أو RPD.

### 2. خدمة metadata مع cache

عند فتح قائمة الموديلات:

1. استدع `models.list` وصف النتائج التي تدعم `generateContent`.
2. للموديلات التي يسمح بها ورّاق، اقرأ metadata وأدخلها في cache محلي مرتبط بـ`model_id + version`.
3. حدّثه عند بدء جلسة جديدة أو بعد مدة معقولة، مثل 24 ساعة.
4. إذا تعذر الاتصال، استخدم آخر نسخة مخزنة واعرض أنها قديمة.
5. إذا لم توجد نسخة مخزنة، امنع الوضع التلقائي لذلك الموديل بدل اختراع حد توكنات.

لا تحذف سجل التوافق المحلي. وظيفته تحديد أن الموديل يقبل صورًا ويعيد نصًا منظمًا. أما Models API فوظيفته إعطاء الأرقام المتغيرة والتوفر الحالي.

### 3. استيراد حصة AI Studio

أضف في الإعدادات زرًا باسم واضح مثل "استيراد حدود AI Studio". ينفذ الآتي:

1. يقرأ CSV ويبحث عن أعمدة `model-cell`, `category`, `RPM`, `TPM`, `RPD`.
2. يهمل الأعمدة الزخرفية والصفوف الفارغة.
3. يقبل صفوف `Text-out models` فقط.
4. يفك كل قيمة على شكل `used / limit`، مع دعم `K` و`M`.
5. يعرض preview لخريطة اسم العرض إلى Model ID قبل الحفظ.
6. يخزن المقامات كحدود. البسط لقطة استخدام سريعة التقادم، فلا يستخدمه في التخطيط بعد الاستيراد.
7. يسجل `source=ai_studio_csv` ووقت الاستيراد واسم المشروع الذي يختاره المستخدم.

إذا لم يستورد المستخدم ملفًا، تبقى الأرقام الحالية fallback محافظًا فقط، وتظهر الواجهة أن المصدر "افتراضي". عند تغير tier أو إضافة موديل، يعيد المستخدم التصدير والاستيراد. هذا أقرب حل عملي للحدود الفعلية من دون إضافة OAuth وCloud IAM إلى تطبيق سطح المكتب.

### 4. مخطط دفعات متعدد القيود

يبني `BatchPlanner` الدفعة لكل موديل ووضع استخراج على حدة. يوقف إضافة الصفحات عند أول قيد من القيود التالية:

- حد عدد الصفحات الذي اختاره المستخدم، إذا اختار حدًا يدويًا.
- حد حجم inline payload الذي يعتمد التطبيق سياسته.
- هامش آمن من `input_token_limit` بعد `count_tokens` للطلب النهائي.
- ما يستطيع local TPM ledger حجزه من `input_tpm`.
- تقدير إخراج الدفعة مقارنة بـ`output_token_limit`.

لا يكفي ضرب عدد الصور في رقم توكن ثابت. توثق Google أن النص والصور وبقية الوسائط كلها تدخل في الحساب، وتوفر `count_tokens` لحساب الطلب قبل الإرسال. [دليل countTokens](https://ai.google.dev/api/tokens)

يكون تقدير الإخراج خاصًا بالثلاثي `model_id + extraction_mode + document_profile`. يسجل التطبيق بعد كل دفعة:

- `prompt_token_count`.
- `candidates_token_count`.
- `thoughts_token_count`.
- عدد الصفحات المكتملة.
- سبب النهاية والمدة.

يستخدم المخطط مئينًا مرتفعًا من توكنات الإخراج لكل صفحة، لا المتوسط وحده. عندما يكون التفكير فعالًا، يحسب التقدير المحافظ `candidates_token_count + thoughts_token_count` إلى أن تثبت اختبارات كل عائلة موديل سلوك السقف بدقة. توثق Google الحقلين منفصلين، لكنها لا تقدم في الصفحات التي راجعتها صياغة كافية لافتراض أن `max_output_tokens` يعاملهما بالطريقة نفسها في كل عائلة. إذا لم توجد بيانات سابقة، يبدأ المخطط بدفعة معايرة صغيرة ثم يكبر. لا نحتاج إلى رقم عالمي مفترض للصفحة العربية. [وثائق التفكير](https://ai.google.dev/gemini-api/docs/generate-content/thinking)

صيغة القرار المقترحة:

```text
predicted_output = page_output_p95 * page_count + schema_overhead
input_ok  = counted_input <= input_token_limit * input_headroom
output_ok = predicted_output <= output_token_limit * output_headroom
tpm_ok    = counted_input <= locally_available_tpm * tpm_headroom
```

ابدأ بقيم قابلة للإعداد مثل 0.80 لهامش الإدخال و0.75 للإخراج و0.80 لـTPM. هذه سياسة ورّاق وليست أرقام Google. يجب وضعها في مكان واحد واختبار أثرها.

`max_output_tokens` في الطلب لا يبقى 16,384. يحسبه التطبيق من التقدير مع هامش، ثم يقيده دائمًا بـ`model_info.output_token_limit`. لا يرسل سقفًا أكبر من الموديل، ولا يثبت 65,536 لجميع الموديلات.

### 5. local quota ledger

وسع منظم الطلبات الحالي ليتابع داخل نافذة الدقيقة:

- عدد طلبات التوليد المحجوزة لـRPM.
- مجموع توكنات الإدخال المحجوزة أو الفعلية لـTPM.
- عدد طلبات اليوم لـRPD.

قبل الطلب، يحجز المخطط `counted_input`. وبعد الرد، يستبدله بـ`usage_metadata.prompt_token_count` إن توفر. يجب أن يكون الحجز ذريًا حتى لا تبدأ مهمتان في الوقت نفسه على افتراض أن الحصة كاملة لكل واحدة.

هذا ledger لا يرى حركة مشروع Gemini من برامج أخرى. لذلك يخفف الأخطاء لكنه لا يضمن عدم ظهور 429. عند 429 أو 503 يستخدم التطبيق exponential backoff مع jitter، ولا يكرر بلا حد. توصي Google بهذا السلوك للأخطاء المؤقتة. [دليل معالجة أخطاء Gemini](https://ai.google.dev/gemini-api/docs/troubleshooting#retry-strategy)

### 6. مسار الاستريمنج

استبدل طلب الدفعة وحده بـ`generate_content_stream`. لا حاجة إلى تغيير طلب الصفحة المفردة في المرحلة الأولى.

مسار المعالجة:

1. أنشئ request واحدًا يحتوي الصور والتعليمات وJSON schema.
2. اجمع `chunk.text` في buffer خام.
3. مرر النص إلى incremental JSON parser يحتمل Unicode escapes وHTML والأقواس داخل النصوص.
4. عند اكتمال عنصر داخل `pages`، طبّق Pydantic validation وفحص رقم الصفحة.
5. احفظ الصفحة في staging، وأرسل للواجهة حدثًا مثل "استلمت الصفحة 12 من 24".
6. اجمع `usage_metadata` و`finish_reason` من chunks، ولا تفترض وجودهما في أول chunk.
7. عند `STOP`، تحقق من JSON الكامل ومن تطابق مجموعة الصفحات مع الطلب، ثم اعتمد staging في transaction.
8. عند انقطاع stream أو `MAX_TOKENS` أو JSON ناقص، لا تعتبر الدفعة ناجحة. أعد الصفحات الناقصة في دفعات أصغر.

يمكن استخدام مكتبة incremental parser صغيرة مثل `ijson` بعد مراجعة حجمها وترخيصها، أو كتابة state machine محدودة لهذا schema. لا تستخدم `split` على الأقواس أو الفواصل.

### 7. التكيف بعد النتائج

- عند `MAX_TOKENS`، اقسم الصفحات الناقصة إلى نصفين فورًا.
- عند 504 أو انقطاع متكرر، اخفض حجم الدفعة، وزد timeout ضمن حد واضح.
- عند فقد صفحة أو تكرار رقمها، أعد الصفحات المتأثرة فقط بعد إغلاق الدفعة الأصلية كـpartial.
- بعد عدة نجاحات متتالية بهامش إخراج وإدخال جيد، ارفع الهدف تدريجيًا.
- افصل إحصاءات الكتب المطبوعة عن المخطوطات، لأن كثافة الإخراج تختلف.
- لا تغير RPM أو TPM المتفق عليهما استنادًا إلى نجاح دفعة. هذه حصة خارجية، وليست قيمة يتعلمها التطبيق.

## مراحل التنفيذ

### المرحلة 1. طبقة الحدود والبيانات

- إضافة `ModelCapabilities` و`ProjectQuotaProfile` migrations.
- نقل DEFAULT_QUOTAS الحالية إلى fallback موسوم بدل اعتباره الحقيقة.
- إضافة adapter لـ`models.list/get/count_tokens`.
- حفظ metadata مع النسخة ووقت الجلب.
- إضافة مستورد CSV مع preview وربط أسماء العرض بالموديلات.

معيار القبول: اختبار بموديل وهمي حد إخراجه 8,192 يغير التخطيط من دون تعديل ثوابت.

### المرحلة 2. المخطط والـledger

- إنشاء `BatchPlanner` مستقل عن UI وGeminiClient.
- إدخال قيود input/output/TPM/payload في قرار واحد قابل للتفسير.
- إرجاع سبب توقف زيادة الدفعة حتى تعرضه الواجهة والسجل.
- توسيع ledger ليحجز توكنات الإدخال إضافة إلى RPM وRPD.

معيار القبول: لا تنتج الخطة دفعة تتجاوز أي حد في اختبارات الحدود، وتظل النتيجة نفسها بعد إعادة تشغيل التطبيق مع metadata مخزنة.

### المرحلة 3. الاستريمنج وstaging

- إضافة `generate_content_stream` لمسار الدفعات.
- إضافة parser تدريجي وأحداث تقدم على مستوى الصفحة.
- حفظ مؤقت ثم commit نهائي عند `STOP`.
- تقسيم الصفحات الناقصة بعد الانقطاع أو `MAX_TOKENS`.

معيار القبول: stream اختباري يقطع JSON في منتصف كلمة عربية وescape ووسم HTML، ومع ذلك تستخرج الصفحات مرة واحدة وبالترتيب الصحيح.

### المرحلة 4. الواجهة والتشغيل

- جعل "تلقائي" الوضع الافتراضي مع إبقاء حد يدوي للخبير.
- عرض الموديل، عدد صفحات الدفعة، سبب اختيار العدد، واستلام الصفحات لحظة بلحظة.
- عرض مصدر الحصة وتاريخ استيرادها وتحذير عند قدمها.
- إضافة زر إيقاف يغلق stream ويترك الصفحات المعتمدة سابقًا سليمة.

معيار القبول: يستطيع المستخدم رؤية تقدم دفعة طويلة، وإيقافها، ثم استكمال الصفحات غير المعتمدة فقط.

### المرحلة 5. قياس حي محدود

- smoke test اختياري لكل موديل يختاره المستخدم، ولا يعمل ضمن الاختبارات العادية.
- تجربة 4 ثم 8 ثم 16 ثم 24 ثم 32 صفحة من كتاب مطبوع ومخطوط.
- تسجيل نسبة الإخراج إلى السقف، زمن أول chunk، الزمن الكلي، الصفحات الناقصة، 429، 504 و`MAX_TOKENS`.
- اعتماد سقف افتراضي بعد البيانات، مع إبقاء planner هو صاحب القرار النهائي.

## اختبارات يجب ألا تسقط من الخطة

- parsing لقيم `530 / 250K`, `1.06K / 250K`, `0 / 0` والقيم الفارغة.
- تجاهل أقسام grounding وLive API والأعمدة الزخرفية.
- عدم الخلط بين Gemini 3 Flash و`gemini-3-flash-preview`.
- metadata ناقص أو قديم أو غير متاح بسبب الشبكة.
- موديل يدعم `generateContent` لكنه غير معتمد للصور أو Structured Outputs.
- مفتاحان مربوطان بملف حصة المشروع نفسه.
- دفعتان متزامنتان تتنافسان على TPM.
- chunks فارغة وmetadata لا يظهر إلا في النهاية.
- إغلاق stream قبل `STOP`.
- `MAX_TOKENS`, 429, 503, 504 وطلب إيقاف المستخدم.
- صفحة مكتملة مؤقتًا ثم JSON نهائي غير صالح.
- تكرار `pdf_page` أو خروج رقم ليس ضمن الطلب.

## خارج نطاق الإصدار الأول

- قراءة AI Studio آليًا عبر scraping.
- إضافة OAuth وCloud Quotas API.
- استخدام Batch API غير المتزامن. هذه الميزة تستهدف تقدمًا حيًا، بينما Batch API له حصص ومسار تشغيل مستقلان.
- دعم موديلات TTS أو الصور أو Live API في مخطط OCR.
- اعتبار تغيير API key طريقة للحصول على حصة جديدة. الحصة للمشروع.

## النتيجة المتوقعة

بعد التنفيذ، لن يسأل ورّاق "كم صفحة يسمح بها Gemini 3.5 Flash-Lite؟" كرقم ثابت. سيسأل لكل دفعة:

- ما حدود الموديل المحدد الآن؟
- كم توكنًا يحتاج هذا الإدخال فعلًا؟
- كم إخراجًا احتاجت صفحات مشابهة على هذا الموديل؟
- ما الحصة التي أخبرنا بها مشروع AI Studio؟
- ما المتاح محليًا في هذه الدقيقة واليوم؟

ثم يختار أكبر دفعة تقع داخل الهوامش، يعرض تقدمها بالاستريمنج، ويصغرها تلقائيًا إذا أثبتت الاستجابة أن التقدير كان متفائلًا.

## المصادر الرسمية

- [Gemini Models API](https://ai.google.dev/api/models)
- [Understand and count tokens](https://ai.google.dev/gemini-api/docs/tokens)
- [Counting tokens API](https://ai.google.dev/api/tokens)
- [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [GenerateContent and streamGenerateContent](https://ai.google.dev/api/generate-content)
- [Structured Outputs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)
- [Gemini API troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting)
- [Cloud Quotas API](https://cloud.google.com/docs/quotas/reference/rest)
- [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/)

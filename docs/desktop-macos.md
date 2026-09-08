# ورّاق لسطح المكتب على macOS

التطبيق مبني باستخدام Python وPySide6 وQt Quick. يعمل في عملية محلية واحدة، ولا يشغل خادم HTTP أو متصفحًا خارجيًا. يحفظ بياناته في `~/Library/Application Support/Warraq`.

## تشغيل نسخة التطوير

افتح مجلد `Mac Commands` وانقر مرتين على `Start-Warraq.command`. ينشئ المشغل بيئة `.venv-desktop` ويثبت اعتماديات سطح المكتب ثم يفتح التطبيق.

للتشغيل من الطرفية:

```sh
python3 -m venv .venv-desktop
.venv-desktop/bin/python -m pip install -r requirements-desktop.txt
.venv-desktop/bin/python run_desktop.py
```

## إنشاء حزمة macOS

```sh
./scripts/build_macos.sh
```

يستخدم البناء `pyside6-deploy` المبني على Nuitka. أنشئ الحزمة على جهاز Mac بنفس المعمارية المستهدفة. يلزم توقيع التطبيق وتوثيقه لدى Apple قبل توزيعه خارج جهاز المطور. لا يتضمن المستودع هوية توقيع أو بيانات حساب Apple.

## البيانات والأسرار

- تحفظ قاعدة SQLite داخل `~/Library/Application Support/Warraq`، ولا تُحفظ داخل `Warraq.app`.
- لا ينسخ ورّاق ملفات PDF. إذا تغيّر مكان الملف، افتح الكتاب واضغط «تغيير ملف PDF»، ثم اختر النسخة المطابقة من Finder. تبقى التحويلات والمراجعات محفوظة.
- تُضاف مفاتيح Gemini بأسماء يختارها المستخدم من دون سجل منفصل لمشروع Google. تحفظ الأسرار في Keychain، وتخزن قاعدة البيانات الاسم ومرجع المفتاح فقط.
- عند حذف مفتاح من ورّاق، يحذف التطبيق بياناته المحلية وسرّه من Keychain. لا يلغي هذا المفتاح من Google AI Studio.
- يرسل التطبيق صفحة PDF كاملة إلى Gemini عند بدء التحويل فقط.
- النسخة الاحتياطية ذات الامتداد `.waraq-backup` تتضمن قاعدة البيانات والنصوص والإعدادات فقط، ولا تتضمن ملفات PDF أو أسرار Keychain.

استبدال `Warraq.app` بإصدار أحدث لا يغير مجلد البيانات. يجب ألا يطلب أي مثبت macOS مستقبلي حذف `~/Library/Application Support/Warraq` أثناء التحديث أو الإزالة العادية.

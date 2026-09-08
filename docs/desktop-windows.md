# ورّاق لسطح المكتب على ويندوز

يبني المشروع تطبيق Windows x64 مستقلًا باستخدام `pyside6-deploy` وNuitka، ثم يضعه داخل Setup Wizard باستخدام Inno Setup.

## المتطلبات

- Windows 10 أو Windows 11 بنواة x64.
- Python 3.12 متاح عبر الأمر `py -3.12`.
- أدوات بناء C++ التي يحتاجها Nuitka وQt، وتشمل MSVC و`dumpbin`.
- Inno Setup 6 أو 7 لإنشاء ملف التثبيت النهائي.

## البناء

شغّل PowerShell من جذر المشروع:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\build_windows.ps1
```

ينتج البناء:

```text
dist\windows\app\Warraq.exe
dist\windows\installer\Warraq-Setup-0.1.0.exe
```

إذا لم يجد السكربت Inno Setup، فإنه يبني مجلد التطبيق فقط ويطبع تحذيرًا.

## البناء من دون جهاز ويندوز

يحتوي المشروع على GitHub Actions workflow في `.github/workflows/build-windows.yml`. يعمل البناء على Windows runner سحابي، يشغّل الاختبارات، ويبني التطبيق والمُثبّت، ثم يرفعهما كـArtifact لمدة 14 يومًا.

بعد وضع المشروع في مستودع GitHub:

1. افتح تبويب Actions.
2. اختر `Build Windows installer`.
3. اضغط `Run workflow`.
4. بعد اكتمال المهمة، نزّل `Warraq-Windows-...` من قسم Artifacts.

يعمل الـworkflow أيضًا عند دفع tag يبدأ بحرف `v`، مثل `v0.1.0`.

## التثبيت والترقية

يثبت الـSetup ملفات البرنامج داخل `C:\Program Files\Warraq`. يستخدم كل إصدار نفس `AppId`، لذلك يتعرف المُثبّت على الإصدار السابق ويحدّثه في المكان نفسه.

تبقى بيانات المستخدم منفصلة داخل `%LOCALAPPDATA%\Warraq`. لا يحتوي ملف Inno Setup على أي أمر يحذف هذا المجلد أثناء الترقية أو إزالة البرنامج.

ملف Setup الناتج حاليًا غير موقّع رقميًا، لذلك قد يعرض Windows تحذير SmartScreen. قبل التوزيع العام نحتاج شهادة Code Signing وإضافة خطوة توقيع إلى البناء السحابي.

## ملفات PDF

لا ينسخ ورّاق ملفات PDF إلى مجلد البرنامج أو مجلد بياناته. تحفظ قاعدة البيانات المسار المطلق للملف الأصلي. إذا تغيّر مكان الملف، افتح الكتاب واضغط «تغيير ملف PDF»، ثم اختر النسخة المطابقة من نافذة اختيار الملفات في Windows. تبقى التحويلات والمراجعات محفوظة.

النسخة الاحتياطية `.waraq-backup` تحفظ قاعدة البيانات والنصوص والإعدادات فقط، ولا تضم ملفات PDF أو مفاتيح Gemini.

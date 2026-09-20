import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: window
    width: 1440
    height: 920
    minimumWidth: 1080
    minimumHeight: 700
    visible: true
    title: "ورّاق"
    color: themeColors.canvas
    LayoutMirroring.enabled: true
    LayoutMirroring.childrenInherit: true

    QtObject {
        id: themeColors
        readonly property color ink: "#18203a"
        readonly property color muted: "#687086"
        readonly property color canvas: "#f3f5fa"
        readonly property color paper: "#fffdfa"
        readonly property color white: "#ffffff"
        readonly property color violet: "#6256d9"
        readonly property color violetSoft: "#eceafe"
        readonly property color mint: "#1c9a77"
        readonly property color mintSoft: "#ddf5ed"
        readonly property color orange: "#d97732"
        readonly property color orangeSoft: "#fff0e4"
        readonly property color red: "#bc3f54"
        readonly property color redSoft: "#fde8ec"
        readonly property color border: "#dfe3ee"
    }

    font.family: "IBM Plex Sans Arabic"

    palette {
        window: themeColors.canvas
        windowText: themeColors.ink
        base: themeColors.white
        alternateBase: "#f8f9fc"
        text: themeColors.ink
        button: themeColors.white
        buttonText: themeColors.ink
        brightText: themeColors.white
        highlight: themeColors.violet
        highlightedText: themeColors.white
        placeholderText: themeColors.muted
        mid: themeColors.border
        dark: themeColors.muted
        light: themeColors.white
        toolTipBase: themeColors.ink
        toolTipText: themeColors.white
    }

    component AppButton: Button {
        id: control
        property color fill: themeColors.violet
        property color foregroundColor: themeColors.white
        property bool outlined: false
        implicitHeight: 42
        leftPadding: 18; rightPadding: 18
        font.pixelSize: 15; font.weight: Font.DemiBold
        contentItem: Text {
            text: control.text
            color: control.enabled ? control.foregroundColor : themeColors.muted
            font: control.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: 11
            color: control.outlined ? "transparent" : (control.down ? Qt.darker(control.fill, 1.08) : control.fill)
            border.color: control.outlined ? control.fill : "transparent"
            border.width: 1
        }
        HoverHandler { cursorShape: Qt.PointingHandCursor }
    }

    component GhostButton: AppButton { outlined: true; fill: themeColors.border; foregroundColor: themeColors.ink }

    component AppTextField: TextField {
        id: field
        LayoutMirroring.enabled: false
        LayoutMirroring.childrenInherit: false
        implicitHeight: 42
        leftPadding: 13
        rightPadding: 13
        color: themeColors.ink
        placeholderTextColor: themeColors.muted
        selectionColor: themeColors.violet
        selectedTextColor: themeColors.white
        horizontalAlignment: Text.AlignRight
        verticalAlignment: Text.AlignVCenter
        background: Rectangle {
            radius: 9
            color: field.readOnly ? "#f2f4f8" : themeColors.white
            border.width: field.activeFocus ? 2 : 1
            border.color: field.activeFocus ? themeColors.violet : themeColors.border
        }
    }

    component AppTextArea: TextArea {
        id: area
        LayoutMirroring.enabled: false
        LayoutMirroring.childrenInherit: false
        leftPadding: 13
        rightPadding: 13
        topPadding: 11
        bottomPadding: 11
        color: themeColors.ink
        placeholderTextColor: themeColors.muted
        selectionColor: themeColors.violet
        selectedTextColor: themeColors.white
        horizontalAlignment: Text.AlignRight
        background: Rectangle {
            radius: 10
            color: area.readOnly ? "#f8f9fc" : themeColors.white
            border.width: area.activeFocus ? 2 : 1
            border.color: area.activeFocus ? themeColors.violet : themeColors.border
        }
    }

    component AppPromptEditor: ScrollView {
        id: scrollArea
        property alias text: scrollEditor.text
        property alias readOnly: scrollEditor.readOnly
        property alias placeholderText: scrollEditor.placeholderText
        property alias cursorPosition: scrollEditor.cursorPosition
        property alias editorObjectName: scrollEditor.objectName

        clip: true
        contentWidth: availableWidth
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical.policy: readOnly ? ScrollBar.AlwaysOff : ScrollBar.AsNeeded
        background: Rectangle {
            radius: 10
            color: scrollArea.readOnly ? "#f8f9fc" : themeColors.white
            border.width: scrollEditor.activeFocus ? 2 : 1
            border.color: scrollEditor.activeFocus ? themeColors.violet : themeColors.border
        }

        AppTextArea {
            id: scrollEditor
            width: scrollArea.availableWidth
            wrapMode: TextEdit.Wrap
            background: Rectangle {
                color: scrollArea.readOnly ? "#f8f9fc" : themeColors.white
            }
        }
    }

    component AppComboBox: ComboBox {
        id: combo
        implicitHeight: 42
        leftPadding: 12
        rightPadding: 12
        LayoutMirroring.enabled: false
        LayoutMirroring.childrenInherit: false
        font.pixelSize: 14
        contentItem: Text {
            leftPadding: 34
            rightPadding: 12
            text: combo.displayText
            color: themeColors.ink
            font: combo.font
            // Text items inside the mirrored ComboBox need the logical opposite
            // alignment to render on the physical right edge.
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        indicator: Text {
            x: 12
            anchors.verticalCenter: parent.verticalCenter
            text: "⌄"
            color: themeColors.muted
            font.pixelSize: 18
        }
        delegate: ItemDelegate {
            id: comboOption
            required property var modelData
            required property int index
            width: combo.popup.width - 8
            implicitHeight: 40
            text: combo.textRole ? modelData[combo.textRole] : modelData
            highlighted: combo.highlightedIndex === index
            contentItem: Text {
                text: comboOption.text
                color: themeColors.ink
                font: combo.font
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                radius: 7
                color: comboOption.highlighted ? themeColors.violetSoft : themeColors.white
            }
        }
        popup: Popup {
            y: combo.height + 4
            width: combo.width
            implicitHeight: Math.min(contentItem.implicitHeight + 8, 280)
            padding: 4
            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: combo.popup.visible ? combo.delegateModel : null
                currentIndex: combo.highlightedIndex
                ScrollIndicator.vertical: ScrollIndicator { }
            }
            background: Rectangle {
                color: themeColors.white
                border.color: themeColors.border
                radius: 9
            }
        }
        background: Rectangle {
            radius: 9
            color: themeColors.white
            border.width: combo.activeFocus ? 2 : 1
            border.color: combo.activeFocus ? themeColors.violet : themeColors.border
        }
        HoverHandler { cursorShape: Qt.PointingHandCursor }
    }

    component AppSpinBox: SpinBox {
        id: spin
        LayoutMirroring.enabled: false
        LayoutMirroring.childrenInherit: false
        implicitHeight: 42
        font.pixelSize: 14
        locale: Qt.locale("en_US")
        HoverHandler { cursorShape: Qt.PointingHandCursor }
        textFromValue: function(value, locale) { return latinNumber(value) }
        valueFromText: function(text, locale) {
            let normalized = String(text)
            const arabicDigits = "٠١٢٣٤٥٦٧٨٩"
            const easternArabicDigits = "۰۱۲۳۴۵۶۷۸۹"
            for (let digit = 0; digit < 10; digit++) {
                normalized = normalized.split(arabicDigits[digit]).join(String(digit))
                normalized = normalized.split(easternArabicDigits[digit]).join(String(digit))
            }
            const parsed = parseInt(normalized.replace(/[^0-9-]/g, ""), 10)
            return isNaN(parsed) ? spin.value : parsed
        }
        function commitValue() {
            const parsed = valueFromText(contentItem.text, locale)
            value = Math.max(from, Math.min(to, parsed))
            return value
        }
        contentItem: TextInput {
            z: 2
            text: spin.displayText
            color: themeColors.ink
            selectionColor: themeColors.violet
            selectedTextColor: themeColors.white
            font: spin.font
            horizontalAlignment: Text.AlignRight
            verticalAlignment: Text.AlignVCenter
            readOnly: !spin.editable
            validator: spin.validator
            inputMethodHints: spin.inputMethodHints
            leftPadding: 34
            rightPadding: 12
            onEditingFinished: spin.commitValue()
        }
        background: Rectangle {
            radius: 9
            color: themeColors.white
            border.width: spin.activeFocus ? 2 : 1
            border.color: spin.activeFocus ? themeColors.violet : themeColors.border
        }
    }

    component Card: Rectangle {
        color: themeColors.white
        radius: 18
        border.color: "#e8eaf1"
        border.width: 1
    }

    component SectionTitle: Text {
        color: themeColors.ink
        font.pixelSize: 28
        font.weight: Font.Bold
    }

    component FieldLabel: Text {
        color: themeColors.ink
        font.pixelSize: 14
        font.weight: Font.DemiBold
    }

    component StatusPill: Rectangle {
        property string label: ""
        property color tone: themeColors.violet
        implicitWidth: statusText.implicitWidth + 22
        implicitHeight: 29
        radius: 14
        color: Qt.rgba(tone.r, tone.g, tone.b, 0.13)
        Text { id: statusText; anchors.centerIn: parent; text: parent.label; color: parent.tone; font.pixelSize: 12; font.weight: Font.DemiBold }
    }

    function screenIndex(name) {
        const names = ["library", "book", "convert", "task", "review", "usage", "requests", "settings", "export", "summaries"]
        const index = names.indexOf(name)
        return index < 0 ? 0 : index
    }

    function latinNumber(value) {
        const number = Number(value)
        return isNaN(number) ? "" : number.toLocaleString(Qt.locale("en_US"), "f", 0)
    }

    function prepareConversion(startPage, endPage, overwrite) {
        conversionScreen.rangePrepared = true
        fromPage.value = startPage
        toPage.value = endPage
        overwriteBox.checked = overwrite
        App.go("convert")
    }

    function suggestedExportFileName() {
        let name = String(App.currentBook.name || "كتاب").trim()
        name = name.replace(/[<>:"/\\|?*\x00-\x1f]/g, "-").replace(/[. ]+$/g, "").trim()
        if (!name) name = "كتاب"
        if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$/i.test(name)) name = "_" + name
        const suffix = exportFormat.currentIndex === 1 ? ".md" : exportFormat.currentIndex === 2 ? ".html" : ".docx"
        if (!name.toLowerCase().endsWith(suffix)) name += suffix
        return name
    }

    function selectedExportFormat() {
        return exportFormat.currentIndex === 1 ? "markdown" : exportFormat.currentIndex === 2 ? "html" : "word"
    }

    function selectedExportLabel() {
        return exportFormat.currentIndex === 1 ? "Markdown" : exportFormat.currentIndex === 2 ? "HTML" : "Word"
    }

    function chooseExportDestination() {
        const folder = exportDialog.currentFolder.toString()
        const separator = folder.endsWith("/") ? "" : "/"
        exportDialog.selectedFile = folder + separator + encodeURIComponent(suggestedExportFileName())
        exportDialog.open()
    }

    function openExportScreen() {
        exportPath.text = ""
        exportFrom.value = 1
        exportTo.value = App.currentBook.page_count || 1
        App.go("export")
    }

    function arabicState(state, reviewed) {
        if (reviewed) return "معتمدة"
        if (state === "done") return "تحتاج مراجعة"
        if (state === "failed") return "فشلت"
        if (state === "running") return "جارٍ التحويل"
        return "لم تحوّل"
    }

    function stateColor(state, reviewed) {
        if (reviewed) return themeColors.mint
        if (state === "done") return "#b38318"
        if (state === "failed") return themeColors.red
        return themeColors.muted
    }

    FileDialog {
        id: importDialog
        title: "إضافة كتاب PDF"
        nameFilters: ["PDF (*.pdf)"]
        onAccepted: App.importBook(selectedFile.toString())
    }
    FileDialog {
        id: relinkBookDialog
        title: "اختيار ملف PDF الجديد"
        nameFilters: ["PDF (*.pdf)"]
        onAccepted: App.relinkBookPdf(selectedFile.toString())
    }
    Dialog {
        id: editBookDialog
        parent: Overlay.overlay
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: Math.min(620, parent.width - 48)
        modal: true
        title: "تعديل الكتاب"
        closePolicy: Popup.CloseOnEscape
        onOpened: editBookName.text = App.currentBook.name || ""
        contentItem: ColumnLayout {
            spacing: 14
            FieldLabel { text: "اسم الكتاب" }
            AppTextField {
                id: editBookName
                Layout.fillWidth: true
                placeholderText: "اسم الكتاب"
            }
            FieldLabel { text: "ملف PDF المرتبط" }
            AppTextField {
                Layout.fillWidth: true
                readOnly: true
                text: App.currentBook.source_path || ""
            }
            Text {
                Layout.fillWidth: true
                text: App.currentBook.source_available
                    ? "الملف موجود ويمكن متابعة العرض والتحويل."
                    : "الملف غير موجود في هذا المسار. اختر النسخة المطابقة لإعادة ربط التحويلات القديمة."
                color: App.currentBook.source_available ? themeColors.mint : themeColors.red
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                GhostButton { text: "تغيير ملف PDF"; onClicked: relinkBookDialog.open() }
                Item { Layout.fillWidth: true }
                GhostButton { text: "إلغاء"; onClicked: editBookDialog.close() }
                AppButton {
                    text: "حفظ الاسم"
                    enabled: editBookName.text.trim().length > 0
                    onClicked: {
                        App.renameCurrentBook(editBookName.text)
                        editBookDialog.close()
                    }
                }
            }
        }
    }
    Dialog {
        id: deleteBookDialog
        parent: Overlay.overlay
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: Math.min(520, parent.width - 48)
        modal: true
        title: "حذف الكتاب"
        closePolicy: Popup.CloseOnEscape
        contentItem: ColumnLayout {
            spacing: 18
            Text {
                Layout.fillWidth: true
                text: "هل تريد حذف «" + (App.currentBook.name || "") + "» من المكتبة؟ لن يُحذف ملف PDF من جهازك."
                color: themeColors.ink
                font.pixelSize: 15
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                GhostButton { text: "إلغاء"; onClicked: deleteBookDialog.close() }
                AppButton {
                    text: "حذف الكتاب"
                    fill: themeColors.red
                    onClicked: {
                        deleteBookDialog.close()
                        App.deleteCurrentBook()
                    }
                }
            }
        }
    }
    Dialog {
        id: resetPageDialog
        objectName: "resetPageDialog"
        parent: Overlay.overlay
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: Math.min(540, parent.width - 48)
        modal: true
        title: "إعادة نص الصفحة"
        closePolicy: Popup.CloseOnEscape
        contentItem: ColumnLayout {
            spacing: 18
            Text {
                Layout.fillWidth: true
                text: "سيُحذف تعديلك الحالي في الصفحة "
                    + latinNumber(App.currentPage.number || "")
                    + "، ويعود النص إلى آخر تحويل وصل من الذكاء الاصطناعي."
                color: themeColors.ink
                font.pixelSize: 15
                wrapMode: Text.WordWrap
            }
            Text {
                Layout.fillWidth: true
                text: "لن تتأثر أي صفحة أخرى."
                color: themeColors.muted
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                GhostButton { text: "إلغاء"; onClicked: resetPageDialog.close() }
                AppButton {
                    objectName: "confirmResetPageButton"
                    text: "إعادة النص"
                    fill: themeColors.orange
                    onClicked: {
                        resetPageDialog.close()
                        App.resetCurrentPageToExtraction()
                    }
                }
            }
        }
    }
    FileDialog {
        id: backupSaveDialog
        title: "حفظ النسخة الاحتياطية"
        fileMode: FileDialog.SaveFile
        nameFilters: ["Warraq backup (*.waraq-backup)"]
        onAccepted: App.createBackup(selectedFile.toString())
    }
    FileDialog {
        id: backupOpenDialog
        title: "استعادة نسخة احتياطية"
        nameFilters: ["Warraq backup (*.waraq-backup)"]
        onAccepted: App.restoreBackup(selectedFile.toString())
    }
    FileDialog {
        id: exportDialog
        objectName: "exportDialog"
        title: "حفظ ملف " + selectedExportLabel()
        fileMode: FileDialog.SaveFile
        defaultSuffix: exportFormat.currentIndex === 1 ? "md" : exportFormat.currentIndex === 2 ? "html" : "docx"
        nameFilters: exportFormat.currentIndex === 1
            ? ["Markdown document (*.md)"]
            : exportFormat.currentIndex === 2
                ? ["HTML document (*.html)"]
                : ["Word document (*.docx)"]
        onAccepted: {
            exportPath.text = selectedFile.toString()
        }
    }
    Dialog {
        id: exportConfirmationDialog
        objectName: "exportConfirmationDialog"
        property int startPage: 1
        property int endPage: 1
        property int reviewedCount: 0
        property int unreviewedCount: 0
        property int ungeneratedCount: 0
        parent: Overlay.overlay
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: Math.min(560, parent.width - 48)
        modal: true
        title: "تأكيد التصدير"
        closePolicy: Popup.CloseOnEscape
        onOpened: includeUnreviewedPages.checked = false
        contentItem: ColumnLayout {
            spacing: 16
            Text {
                Layout.fillWidth: true
                text: "سيُنشئ ورّاق ملف " + selectedExportLabel() + " من الصفحات المولّدة داخل النطاق المحدد."
                color: themeColors.ink
                font.pixelSize: 15
                wrapMode: Text.WordWrap
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: exportSummary.implicitHeight + 28
                radius: 12
                color: themeColors.violetSoft
                RowLayout {
                    id: exportSummary
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 20
                    ColumnLayout {
                        spacing: 2
                        Text { text: latinNumber(exportConfirmationDialog.reviewedCount); color: themeColors.mint; font.pixelSize: 22; font.weight: Font.Bold }
                        Text { text: "صفحة معتمدة"; color: themeColors.ink; font.pixelSize: 12 }
                    }
                    ColumnLayout {
                        spacing: 2
                        Text { text: latinNumber(exportConfirmationDialog.unreviewedCount); color: themeColors.orange; font.pixelSize: 22; font.weight: Font.Bold }
                        Text { text: "صفحة غير معتمدة"; color: themeColors.ink; font.pixelSize: 12 }
                    }
                    Item { Layout.fillWidth: true }
                }
            }
            CheckBox {
                id: includeUnreviewedPages
                objectName: "includeUnreviewedPages"
                visible: exportConfirmationDialog.unreviewedCount > 0
                text: "تضمين الصفحات المولّدة غير المعتمدة"
                font.pixelSize: 14
            }
            Text {
                Layout.fillWidth: true
                visible: exportConfirmationDialog.ungeneratedCount > 0
                text: "لن تُضاف " + latinNumber(exportConfirmationDialog.ungeneratedCount) + " صفحة لأنها لم تُولّد بعد."
                color: themeColors.muted
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                GhostButton { text: "رجوع"; onClicked: exportConfirmationDialog.close() }
                AppButton {
                    objectName: "confirmExportButton"
                    text: "تأكيد التصدير"
                    foregroundColor: themeColors.white
                    enabled: exportConfirmationDialog.reviewedCount > 0
                        || (includeUnreviewedPages.checked && exportConfirmationDialog.unreviewedCount > 0)
                    onClicked: {
                        exportConfirmationDialog.close()
                        App.exportBook(JSON.stringify({
                            book_id: App.currentBook.id,
                            start_page: exportConfirmationDialog.startPage,
                            end_page: exportConfirmationDialog.endPage,
                            destination: exportPath.text,
                            format: selectedExportFormat(),
                            include_unreviewed: includeUnreviewedPages.checked
                        }))
                    }
                }
            }
        }
    }
    Dialog {
        id: deleteKeyDialog
        property string keyId: ""
        property string keyName: ""
        parent: Overlay.overlay
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: Math.min(520, parent.width - 48)
        modal: true
        title: "حذف مفتاح Gemini"
        closePolicy: Popup.CloseOnEscape
        contentItem: ColumnLayout {
            spacing: 18
            Text {
                Layout.fillWidth: true
                text: "سيُحذف المفتاح «" + deleteKeyDialog.keyName + "» من ورّاق ومن مخزن كلمات المرور في النظام. لا يلغي هذا المفتاح من Google AI Studio."
                color: themeColors.ink
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                GhostButton { text: "إلغاء"; onClicked: deleteKeyDialog.close() }
                AppButton {
                    text: "حذف المفتاح"
                    fill: themeColors.red
                    onClicked: {
                        deleteKeyDialog.close()
                        App.deleteKey(deleteKeyDialog.keyId)
                    }
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 72
            color: "#f9ffffff"
            border.color: "#e5e7ef"
            RowLayout {
                anchors.fill: parent
                anchors.rightMargin: 24; anchors.leftMargin: 24
                spacing: 14
                Text {
                    text: "ورّاق"
                    color: themeColors.ink
                    font.family: "Noto Naskh Arabic"
                    font.pixelSize: 30
                    font.weight: Font.Bold
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: App.go("library") }
                }
                Rectangle { width: 1; height: 28; color: themeColors.border }
                Text {
                    Layout.fillWidth: true
                    text: App.currentBook.name || "مكتبتك المحلية"
                    color: themeColors.muted
                    font.pixelSize: 14
                    elide: Text.ElideRight
                }
                Text { text: App.saveState; color: App.saveState === "تعذر الحفظ" ? themeColors.red : themeColors.muted; font.pixelSize: 12; visible: App.screen === "review" }
                AppButton { text: "تحويل صفحات"; onClicked: App.go("convert") }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            Rectangle {
                Layout.preferredWidth: 226
                Layout.fillHeight: true
                color: "#eef0f7"
                border.color: "#e1e4ed"
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 8
                    Repeater {
                        model: [
                            {screen:"library", label:"الكتب", mark:"ك"},
                            {screen:"review", label:"المراجعة", mark:"ر"},
                            {screen:"summaries", label:"الملخصات", mark:"خ"},
                            {screen:"task", label:"عمليات التحويل", mark:"ت"},
                            {screen:"usage", label:"الاستهلاك", mark:"ح"},
                            {screen:"requests", label:"سجل الطلبات", mark:"س"},
                            {screen:"settings", label:"الإعدادات", mark:"ع"}
                        ]
                        delegate: Button {
                            id: navButton
                            required property var modelData
                            Layout.fillWidth: true
                            implicitHeight: 48
                            leftPadding: 12; rightPadding: 12
                            onClicked: {
                                if (modelData.screen === "review" && App.currentBook.id) App.openPage(App.currentBook.last_page || 1)
                                else App.go(modelData.screen)
                            }
                            contentItem: RowLayout {
                                spacing: 12
                                Rectangle {
                                    width: 28; height: 28; radius: 8
                                    color: App.screen === modelData.screen ? themeColors.violet : "#dde1ec"
                                    Text { anchors.centerIn: parent; text: modelData.mark; color: App.screen === modelData.screen ? "white" : themeColors.ink; font.weight: Font.Bold }
                                }
                                Text { Layout.fillWidth: true; text: modelData.label; color: themeColors.ink; font.pixelSize: 15; font.weight: App.screen === modelData.screen ? Font.DemiBold : Font.Normal }
                            }
                            background: Rectangle { radius: 12; color: App.screen === modelData.screen ? themeColors.white : (navButton.hovered ? "#f8f9fc" : "transparent") }
                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                        }
                    }
                    Item { Layout.fillHeight: true }
                    Card {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 118
                        color: themeColors.paper
                        Column {
                            anchors.fill: parent; anchors.margins: 14; spacing: 6
                            Text { text: "محلي بالكامل"; color: themeColors.ink; font.weight: Font.DemiBold }
                            Text { width: parent.width; text: "لا يُرسل إلى Gemini إلا الصفحات أو الملخصات التي تختار معالجتها."; color: themeColors.muted; font.pixelSize: 11; wrapMode: Text.WordWrap }
                        }
                    }
                }
            }

            StackLayout {
                id: stack
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: screenIndex(App.screen)

                // Library
                Item {
                    ScrollView {
                        anchors.fill: parent
                        contentWidth: availableWidth
                        ColumnLayout {
                            width: Math.min(1080, stack.width - 72)
                            x: (stack.width - width) / 2
                            spacing: 20
                            Item { Layout.preferredHeight: 18 }
                            RowLayout {
                                Layout.fillWidth: true
                                ColumnLayout {
                                    Layout.fillWidth: true; spacing: 2
                                    SectionTitle { text: "الكتب" }
                                    Text { text: latinNumber(App.books.length) + " كتابًا في المكتبة"; color: themeColors.muted }
                                }
                                AppButton { text: "إضافة كتاب"; onClicked: importDialog.open() }
                            }
                            Card {
                                Layout.fillWidth: true
                                Layout.preferredHeight: Math.max(170, booksColumn.implicitHeight + 28)
                                ColumnLayout {
                                    id: booksColumn
                                    anchors.fill: parent; anchors.margins: 14; spacing: 8
                                    RowLayout {
                                        Layout.fillWidth: true
                                        AppTextField { id: searchBooks; Layout.fillWidth: true; placeholderText: "ابحث باسم الكتاب"; onAccepted: App.refresh() }
                                        GhostButton { text: "الكل" }
                                    }
                                    Repeater {
                                        model: App.books
                                        delegate: Rectangle {
                                            id: bookRow
                                            required property var modelData
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 112
                                            radius: 14
                                            color: bookMouse.containsMouse ? "#f8f8fd" : themeColors.white
                                            border.color: "#eceef4"
                                            MouseArea { id: bookMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: App.openBook(modelData.id) }
                                            RowLayout {
                                                anchors.fill: parent; anchors.margins: 16; spacing: 16
                                                Rectangle {
                                                    width: 56; height: 74; radius: 5; color: themeColors.violetSoft
                                                    Rectangle { width: 5; height: parent.height; anchors.right: parent.right; color: themeColors.violet; radius: 2 }
                                                    Text { anchors.centerIn: parent; text: "و"; color: themeColors.violet; font.family: "Noto Naskh Arabic"; font.pixelSize: 28; font.bold: true }
                                                }
                                                ColumnLayout {
                                                    Layout.fillWidth: true; spacing: 7
                                                    RowLayout {
                                                        Layout.fillWidth: true
                                                        Text { Layout.fillWidth: true; text: modelData.name; color: themeColors.ink; font.pixelSize: 18; font.weight: Font.DemiBold; elide: Text.ElideRight }
                                                        StatusPill { label: !modelData.source_available ? "ملف PDF مفقود" : (modelData.reviewed === modelData.page_count ? "مكتمل ومراجع" : (modelData.failed ? "به صفحات فاشلة" : "قيد العمل")); tone: !modelData.source_available ? themeColors.red : (modelData.reviewed === modelData.page_count ? themeColors.mint : (modelData.failed ? themeColors.red : "#a37713")) }
                                                    }
                                                    Text { text: latinNumber(modelData.page_count) + " صفحة، آخر صفحة " + latinNumber(modelData.last_page); color: themeColors.muted; font.pixelSize: 12 }
                                                    RowLayout {
                                                        Layout.fillWidth: true; spacing: 10
                                                        Text { text: "التحويل " + latinNumber(modelData.converted) + "/" + latinNumber(modelData.page_count); color: themeColors.muted; font.pixelSize: 11 }
                                                        ProgressBar { Layout.fillWidth: true; from: 0; to: modelData.page_count; value: modelData.converted }
                                                        Text { text: "المراجعة " + latinNumber(modelData.reviewed) + "/" + latinNumber(modelData.page_count); color: themeColors.muted; font.pixelSize: 11 }
                                                        ProgressBar { Layout.fillWidth: true; from: 0; to: modelData.page_count; value: modelData.reviewed }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    ColumnLayout {
                                        visible: App.books.length === 0
                                        Layout.alignment: Qt.AlignHCenter
                                        Layout.topMargin: 24; Layout.bottomMargin: 24
                                        Text { text: "ابدأ بكتاب واحد"; color: themeColors.ink; font.pixelSize: 21; font.weight: Font.DemiBold; Layout.alignment: Qt.AlignHCenter }
                                        Text { text: "أضف ملف PDF من مكانه الحالي. لن ينشئ ورّاق نسخة أخرى منه، فلا تنقله بعد إضافته."; color: themeColors.muted; Layout.alignment: Qt.AlignHCenter }
                                        AppButton { text: "اختيار PDF"; Layout.alignment: Qt.AlignHCenter; onClicked: importDialog.open() }
                                    }
                                }
                            }
                        }
                    }
                }

                // Book detail
                Item {
                    ScrollView { anchors.fill: parent; contentWidth: availableWidth
                        ColumnLayout {
                            width: Math.min(1120, stack.width - 72); x: (stack.width - width) / 2; spacing: 18
                            Item { Layout.preferredHeight: 18 }
                            GhostButton { text: "العودة إلى المكتبة"; Layout.alignment: Qt.AlignRight; onClicked: App.go("library") }
                            Card {
                                Layout.fillWidth: true; Layout.preferredHeight: 220
                                ColumnLayout { anchors.fill: parent; anchors.margins: 24; spacing: 12
                                    RowLayout { Layout.fillWidth: true; spacing: 18
                                        ColumnLayout { Layout.fillWidth: true
                                            StatusPill { label: !App.currentBook.source_available ? "ملف PDF مفقود" : "قيد العمل"; tone: !App.currentBook.source_available ? themeColors.red : "#a37713" }
                                            SectionTitle { text: App.currentBook.name || "" }
                                            Text { text: latinNumber(App.currentBook.page_count || 0) + " صفحة، آخر صفحة " + latinNumber(App.currentBook.last_page || 1); color: themeColors.muted }
                                        }
                                        AppButton { text: "استئناف المراجعة"; enabled: !!App.currentBook.source_available; fill: themeColors.mint; onClicked: App.openPage(App.currentBook.last_page || 1) }
                                        AppButton { text: "تحويل صفحات"; enabled: !!App.currentBook.source_available; onClicked: App.go("convert") }
                                        GhostButton { text: "الملخصات"; onClicked: App.openSummaries(App.currentBook.id) }
                                        GhostButton { text: "تصدير"; onClicked: openExportScreen() }
                                    }
                                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: themeColors.border }
                                    RowLayout { Layout.fillWidth: true; spacing: 10
                                        Text {
                                            Layout.fillWidth: true
                                            text: App.currentBook.source_path || ""
                                            color: App.currentBook.source_available ? themeColors.muted : themeColors.red
                                            font.pixelSize: 11
                                            elide: Text.ElideMiddle
                                        }
                                        GhostButton { text: "تعديل الكتاب"; onClicked: editBookDialog.open() }
                                        GhostButton { text: "تغيير ملف PDF"; fill: App.currentBook.source_available ? themeColors.border : themeColors.red; foregroundColor: App.currentBook.source_available ? themeColors.ink : themeColors.red; onClicked: relinkBookDialog.open() }
                                        GhostButton { text: "حذف الكتاب"; fill: themeColors.red; foregroundColor: themeColors.red; onClicked: deleteBookDialog.open() }
                                    }
                                }
                            }
                            Card {
                                Layout.fillWidth: true; Layout.preferredHeight: Math.max(210, pageFlow.implicitHeight + 78)
                                ColumnLayout { anchors.fill: parent; anchors.margins: 22; spacing: 16
                                    Text { text: "حالة الصفحات"; color: themeColors.ink; font.pixelSize: 20; font.weight: Font.DemiBold }
                                    Flow {
                                        id: pageFlow
                                        Layout.fillWidth: true; spacing: 8
                                        Repeater {
                                            model: App.currentBook.pages || []
                                            delegate: Button {
                                                id: pageButton
                                                required property var modelData
                                                width: 54; height: 42
                                                text: latinNumber(modelData.number)
                                                onClicked: App.openPage(modelData.number)
                                                contentItem: Text { text: pageButton.text; color: stateColor(modelData.state, modelData.reviewed); horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.weight: Font.DemiBold }
                                                background: Rectangle { radius: 9; property color tone: stateColor(modelData.state, modelData.reviewed); color: Qt.rgba(tone.r,tone.g,tone.b,.1); border.color: tone }
                                                ToolTip.visible: hovered; ToolTip.text: arabicState(modelData.state, modelData.reviewed)
                                                HoverHandler { cursorShape: Qt.PointingHandCursor }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Conversion setup
                Item {
                    id: conversionScreen
                    property string requestedModelKey: ""
                    property string preparedTaskModelId: ""
                    property bool rangePrepared: false
                    property string selectedMode: operationBox.currentIndex === 1 ? "translation"
                        : operationBox.currentIndex === 2 ? "summary"
                        : manuscriptMode.checked ? "manuscript" : "printed"
                    property var matchingPrompts: App.prompts.filter(function(prompt) {
                        return prompt.mode === conversionScreen.selectedMode
                    })
                    property var selectedBook: convertBook.currentIndex >= 0 && App.books[convertBook.currentIndex]
                        ? App.books[convertBook.currentIndex] : App.currentBook
                    function indexForValue(items, field, value) {
                        for (let index = 0; index < items.length; index++) {
                            if (items[index][field] === value) return index
                        }
                        return -1
                    }
                    function selectPreparedTaskModel() {
                        if (!preparedTaskModelId) return
                        const index = indexForValue(modelBox.model, "id", preparedTaskModelId)
                        if (index >= 0) modelBox.currentIndex = index
                        if (!App.busy && App.models.length > 0) preparedTaskModelId = ""
                    }
                    function prepareFromTask() {
                        const task = App.currentTask
                        if (!task.id) return
                        if (task.summary_input_ids && task.summary_input_ids !== "[]") {
                            summariesPanel.prepareReview(task)
                            return
                        }
                        rangePrepared = true
                        requestedModelKey = ""
                        preparedTaskModelId = task.model || ""
                        App.openBook(task.book_id)
                        fromPage.value = task.start_page
                        toPage.value = task.end_page
                        overwriteBox.checked = false
                        pagesPerRequest.value = task.pages_per_request || 1
                        operationBox.currentIndex = task.mode === "translation" ? 1 : task.mode === "summary" ? 2 : 0
                        manuscriptMode.checked = task.mode === "manuscript"
                        languageBox.currentIndex = indexForValue(languageBox.model, "name", task.target_language || "العربية")
                        if (languageBox.currentIndex < 0) {
                            languageBox.currentIndex = languageBox.model.length - 1
                            otherLanguage.text = task.target_language || ""
                        }
                        directionBox.currentIndex = task.text_direction === "ltr" ? 1 : 0
                        summaryBox.currentIndex = indexForValue(summaryBox.model, "id", task.summary_level || "medium")
                        additionalInstructions.text = task.additional_instructions || ""
                        keyBox.currentIndex = indexForValue(App.keys, "id", task.key_id)
                        promptBox.currentIndex = indexForValue(conversionScreen.matchingPrompts, "id", task.prompt_id)
                        dpiBox.currentIndex = indexForValue(dpiBox.model, "value", task.dpi)
                        App.go("convert")
                        Qt.callLater(selectPreparedTaskModel)
                    }
                    function initializeRange() {
                        const book = selectedBook || {}
                        const start = book.last_page || 1
                        fromPage.value = Math.max(1, Math.min(start, book.page_count || 9999))
                        toPage.value = Math.max(fromPage.value, Math.min(fromPage.value + 9, book.page_count || 9999))
                    }
                    function loadModels(force) {
                        if (App.screen !== "convert" || keyBox.currentIndex < 0 || !keyBox.model[keyBox.currentIndex]) return
                        const keyId = keyBox.model[keyBox.currentIndex].id
                        if (!force && requestedModelKey === keyId) return
                        requestedModelKey = keyId
                        App.refreshModels(keyId)
                    }
                    onVisibleChanged: if (visible) Qt.callLater(function() {
                        if (!conversionScreen.rangePrepared) conversionScreen.initializeRange()
                        conversionScreen.rangePrepared = false
                        conversionScreen.loadModels(false)
                        conversionScreen.selectPreparedTaskModel()
                    })
                    Connections {
                        target: App
                        function onStateChanged() {
                            if (conversionScreen.visible && conversionScreen.preparedTaskModelId)
                                Qt.callLater(conversionScreen.selectPreparedTaskModel)
                        }
                    }
                    Flickable { anchors.fill: parent; contentWidth: width; contentHeight: conversionColumn.implicitHeight + 70; clip: true
                        ColumnLayout {
                            id: conversionColumn
                            width: Math.min(900, stack.width - 90); x: (stack.width - width) / 2; y: 28; spacing: 18
                            SectionTitle { text: "تحويل صفحات" }
                            Text { Layout.fillWidth: true; text: "اختر أي صفحة أو نطاق. عند إعادة التحويل يحفظ ورّاق النتيجة السابقة في السجل، فلا تفقد النسخة التي راجعتها أو نتيجة المحاولة القديمة."; color: themeColors.muted; wrapMode: Text.WordWrap }
                            RowLayout { Layout.fillWidth: true; spacing: 8
                                GhostButton { visible: !!App.currentPage.number && conversionScreen.selectedBook.id === App.currentBook.id; text: "الصفحة الحالية فقط"; onClicked: { fromPage.value = App.currentPage.number; toPage.value = App.currentPage.number } }
                                GhostButton { text: "الكتاب كاملًا"; onClicked: { fromPage.value = 1; toPage.value = conversionScreen.selectedBook.page_count || 1 } }
                                Item { Layout.fillWidth: true }
                            }
                            Card {
                                Layout.fillWidth: true; Layout.preferredHeight: conversionForm.implicitHeight + 48
                                GridLayout {
                                    id: conversionForm
                                    anchors.fill: parent; anchors.margins: 24; columns: 2; rowSpacing: 12; columnSpacing: 16
                                    FieldLabel { text: "الكتاب" }
                                    AppComboBox {
                                        id: convertBook
                                        Layout.fillWidth: true
                                        model: App.books
                                        textRole: "name"
                                        currentIndex: {
                                            for (let index = 0; index < App.books.length; index++) {
                                                if (App.books[index].id === App.currentBook.id) return index
                                            }
                                            return App.books.length ? 0 : -1
                                        }
                                        onActivated: {
                                            const selected = App.books[currentIndex]
                                            fromPage.value = selected.last_page || 1
                                            toPage.value = Math.min((selected.last_page || 1) + 9, selected.page_count)
                                        }
                                    }
                                    FieldLabel { text: "من صفحة PDF" }
                                    AppSpinBox { id: fromPage; objectName: "conversionFromPage"; Layout.fillWidth: true; from: 1; to: conversionScreen.selectedBook.page_count || 9999; value: 1; editable: true }
                                    FieldLabel { text: "إلى صفحة PDF" }
                                    AppSpinBox { id: toPage; objectName: "conversionToPage"; Layout.fillWidth: true; from: 1; to: conversionScreen.selectedBook.page_count || 9999; value: 1; editable: true }
                                    FieldLabel { text: "مفتاح Gemini" }
                                    AppComboBox { id: keyBox; Layout.fillWidth: true; model: App.keys; textRole: "name"; onCurrentIndexChanged: conversionScreen.loadModels(false) }
                                    FieldLabel { text: "نموذج Gemini" }
                                    RowLayout { Layout.fillWidth: true
                                        AppComboBox { id: modelBox; objectName: "conversionModelBox"; Layout.fillWidth: true; model: App.models.length ? App.models : [{id:"gemini-3.5-flash-lite", label:"Gemini 3.5 Flash Lite (500 استعلام يوميًا) · gemini-3.5-flash-lite"}]; textRole: "label" }
                                        GhostButton { text: App.busy ? "جارٍ التحديث" : "تحديث"; enabled: !App.busy && keyBox.currentIndex >= 0; onClicked: conversionScreen.loadModels(true) }
                                    }
                                    FieldLabel { text: "العملية" }
                                    AppComboBox {
                                        id: operationBox
                                        objectName: "conversionOperationBox"
                                        Layout.fillWidth: true
                                        model: [{name:"نسخ النص"},{name:"ترجمة"},{name:"تلخيص"}]
                                        textRole: "name"
                                        onActivated: {
                                            promptBox.currentIndex = 0
                                            if (currentIndex === 2)
                                                pagesPerRequest.value = Math.min(10, Math.max(1, toPage.value - fromPage.value + 1))
                                        }
                                    }
                                    FieldLabel { text: "نوع الأصل"; visible: operationBox.currentIndex === 0 }
                                    RowLayout {
                                        visible: operationBox.currentIndex === 0
                                        RadioButton { id: printedMode; text: "كتاب مطبوع"; checked: true; HoverHandler { cursorShape: Qt.PointingHandCursor } }
                                        RadioButton { id: manuscriptMode; text: "مخطوط"; HoverHandler { cursorShape: Qt.PointingHandCursor } }
                                    }
                                    FieldLabel { text: "لغة الترجمة"; visible: operationBox.currentIndex === 1 }
                                    AppComboBox {
                                        id: languageBox
                                        objectName: "translationLanguageBox"
                                        visible: operationBox.currentIndex === 1
                                        Layout.fillWidth: true
                                        model: [{name:"العربية"},{name:"الإنجليزية"},{name:"الفرنسية"},{name:"الألمانية"},{name:"الإسبانية"},{name:"التركية"},{name:"الأردية"},{name:"الفارسية"},{name:"الإندونيسية"},{name:"أخرى"}]
                                        textRole: "name"
                                        onActivated: {
                                            if (currentIndex < model.length - 1)
                                                directionBox.currentIndex = ["العربية", "الأردية", "الفارسية"].includes(model[currentIndex].name) ? 0 : 1
                                        }
                                    }
                                    FieldLabel { text: "اسم اللغة"; visible: operationBox.currentIndex === 1 && languageBox.currentIndex === languageBox.model.length - 1 }
                                    AppTextField {
                                        id: otherLanguage
                                        objectName: "otherTranslationLanguage"
                                        visible: operationBox.currentIndex === 1 && languageBox.currentIndex === languageBox.model.length - 1
                                        Layout.fillWidth: true
                                        placeholderText: "اكتب اللغة المطلوبة"
                                    }
                                    FieldLabel { text: "اتجاه النص"; visible: operationBox.currentIndex === 1 }
                                    AppComboBox {
                                        id: directionBox
                                        objectName: "translationDirectionBox"
                                        visible: operationBox.currentIndex === 1
                                        Layout.fillWidth: true
                                        model: [{id:"rtl",name:"من اليمين إلى اليسار"},{id:"ltr",name:"من اليسار إلى اليمين"}]
                                        textRole: "name"
                                    }
                                    FieldLabel { text: "تفصيل الصياغة"; visible: operationBox.currentIndex === 2 }
                                    AppComboBox {
                                        id: summaryBox
                                        objectName: "summaryLevelBox"
                                        visible: operationBox.currentIndex === 2
                                        Layout.fillWidth: true
                                        model: [{id:"light",name:"موسع"},{id:"medium",name:"متوازن"},{id:"strong",name:"مكثف مع حفظ المعلومات"}]
                                        textRole: "name"
                                        currentIndex: 1
                                    }
                                    Text { Layout.columnSpan: 2; Layout.fillWidth: true; visible: operationBox.currentIndex === 2; wrapMode: Text.WordWrap; color: themeColors.muted; text: "ملخص موحد لكل دفعة بالأرباع الأربعة، مع إحالات PDF. يُقترح نحو 10 صفحات مترابطة في الاستعلام كي يكتمل المبحث وتتحسن دقة الاختيار. تُحفظ الملخصات مستقلة، ويمكن دمجها لاحقًا من شاشة الملخصات." }
                                    FieldLabel { text: "نسخة البرومبت" }
                                    AppComboBox { id: promptBox; objectName: "conversionPromptBox"; Layout.fillWidth: true; model: conversionScreen.matchingPrompts; textRole: "name" }
                                    SectionTitle { text: "الإعدادات المتقدمة"; Layout.columnSpan: 2; Layout.fillWidth: true; Layout.topMargin: 12 }
                                    FieldLabel { text: "دقة الصورة" }
                                    AppComboBox { id: dpiBox; Layout.fillWidth: true; model: [{label:"200 DPI، أسرع", value:200},{label:"300 DPI، متوازن",value:300},{label:"400 DPI، أدق",value:400}]; textRole: "label"; currentIndex: 1 }
                                    FieldLabel { text: "عدد الصفحات في الاستعلام" }
                                    AppSpinBox { id: pagesPerRequest; objectName: "conversionPagesPerRequest"; Layout.fillWidth: true; from: 1; to: Math.max(1, toPage.value - fromPage.value + 1); value: 1; editable: true }
                                    FieldLabel { text: "الصفحات المكتملة"; visible: conversionScreen.selectedMode !== "summary" }
                                    CheckBox { id: overwriteBox; visible: conversionScreen.selectedMode !== "summary"; text: "إعادة تحويل الصفحات المكتملة داخل النطاق مع حفظ محاولاتها السابقة" }
                                    FieldLabel { text: "تعليمات إضافية للذكاء الاصطناعي"; Layout.alignment: Qt.AlignTop }
                                    AppTextArea {
                                        id: additionalInstructions
                                        objectName: "conversionAdditionalInstructions"
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 112
                                        wrapMode: TextEdit.Wrap
                                        placeholderText: "تعليمات خاصة بهذه المهمة، تُضاف إلى البرومبت المختار"
                                    }
                                }
                            }
                            Text { Layout.fillWidth: true; text: "يرسل ورّاق صفحات الاستعلام كصور مستقلة. قد تفشل الأعداد الكبيرة إذا تجاوز النص الناتج الحد الذي يقبله النموذج."; color: themeColors.muted; wrapMode: Text.WordWrap }
                            RowLayout { Layout.fillWidth: true
                                Text { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: conversionScreen.selectedMode === "summary" ? "سيُلخّص النطاق كاملًا في نتائج مستقلة مع بقاء النصوص السابقة." : overwriteBox.checked ? "سيعاد تحويل كل صفحات النطاق المحدد." : "سيتجاوز ورّاق الصفحات المكتملة ويحوّل المعلقة أو الفاشلة فقط."; color: themeColors.muted }
                                GhostButton { text: "إلغاء"; onClicked: App.go(App.currentBook.id ? "book" : "library") }
                                AppButton {
                                    objectName: "startConversionButton"
                                    text: "بدء التحويل"
                                    enabled: App.books.length > 0 && keyBox.currentIndex >= 0 && promptBox.currentIndex >= 0
                                        && (conversionScreen.selectedMode !== "translation" || languageBox.currentIndex !== languageBox.model.length - 1 || otherLanguage.text.trim().length > 0)
                                    onClicked: {
                                        const book = conversionScreen.selectedBook
                                        const key = App.keys[keyBox.currentIndex]
                                        const prompt = promptBox.model[promptBox.currentIndex]
                                        const model = modelBox.model[modelBox.currentIndex]
                                        const startPage = fromPage.commitValue()
                                        const endPage = toPage.commitValue()
                                        const requestPageCount = pagesPerRequest.commitValue()
                                        const language = languageBox.currentIndex === languageBox.model.length - 1 ? otherLanguage.text.trim() : languageBox.model[languageBox.currentIndex].name
                                        App.startConversion(JSON.stringify({book_id:book.id,start_page:startPage,end_page:endPage,key_id:key.id,model:model.id,prompt_id:prompt.id,mode:conversionScreen.selectedMode,target_language:conversionScreen.selectedMode === "translation" ? language : "",text_direction:directionBox.model[directionBox.currentIndex].id,summary_level:conversionScreen.selectedMode === "summary" ? summaryBox.model[summaryBox.currentIndex].id : "",additional_instructions:additionalInstructions.text,dpi:dpiBox.model[dpiBox.currentIndex].value,overwrite:overwriteBox.checked,pages_per_request:requestPageCount}))
                                    }
                                }
                            }
                        }
                    }
                }

                // Task
                Item {
                    id: taskScreen
                    property bool conversionActive: ["queued", "running"].includes(App.currentTask.state)
                    property bool conversionPaused: ["paused", "interrupted"].includes(App.currentTask.state)
                    property bool conversionHasErrors: ["failed", "completed_with_errors"].includes(App.currentTask.state)
                    function activePagesLabel() {
                        const pages = App.currentTask.active_pages || []
                        return pages.length
                            ? pages.map(function(number) { return latinNumber(number) }).join("، ")
                            : "لا توجد"
                    }
                    function taskStateLabel() {
                        if (App.currentTask.summary_review_version === 2 && App.currentTask.state === "running" && !App.currentTask.control_action)
                            return "جارٍ مراجعة الدفعة " + latinNumber(App.currentTask.review_current || 1) + " من " + latinNumber(App.currentTask.total || 1)
                        if (App.currentTask.summary_contract && App.currentTask.state === "completed") return "اكتملت الملخصات"
                        if (App.currentTask.summary_contract && App.currentTask.state === "running" && !App.currentTask.control_action) return App.currentTask.summary_input_ids !== "[]" ? "جارٍ مراجعة الملخصات المحددة" : "جارٍ تلخيص الدفعة الحالية"
                        if (App.currentTask.state === "queued") return "جارٍ تجهيز مهمة التحويل"
                        if (App.currentTask.state === "running") {
                            if (App.currentTask.control_action === "pause") return "جارٍ تعليق المهمة بعد الدفعة الحالية"
                            if (App.currentTask.control_action === "cancel") return "جارٍ إلغاء المهمة بعد الدفعة الحالية"
                            const pages = App.currentTask.active_pages || []
                            if (pages.length > 1) {
                                return "جارٍ تحويل " + latinNumber(pages.length) + " صفحات، من "
                                    + latinNumber(pages[0]) + " إلى " + latinNumber(pages[pages.length - 1])
                            }
                            return App.currentTask.current_page
                                ? "جارٍ تحويل الصفحة " + latinNumber(App.currentTask.current_page)
                                : "جارٍ بدء تحويل الصفحات"
                        }
                        if (App.currentTask.state === "paused") return "توقف التحويل مؤقتًا"
                        if (App.currentTask.state === "interrupted") return "توقف التحويل قبل اكتماله"
                        if (App.currentTask.state === "cancelled") return "أُلغيت المهمة وحُفظ ما اكتمل منها"
                        if (App.currentTask.state === "completed") return "اكتمل تحويل الصفحات"
                        if (App.currentTask.state === "completed_with_errors") return "اكتمل التحويل مع صفحات تحتاج إعادة المحاولة"
                        if (App.currentTask.state === "failed") return "تعذر إكمال التحويل"
                        return "مهمة التحويل جاهزة"
                    }
                    ColumnLayout { width: Math.min(930, stack.width - 80); anchors.centerIn: parent; spacing: 18
                        RowLayout {
                            Layout.fillWidth: true
                            SectionTitle { text: "عمليات التحويل" }
                            Item { Layout.fillWidth: true }
                            AppButton { text: "مهمة جديدة"; onClicked: App.go("convert") }
                        }
                        AppComboBox {
                            objectName: "taskPicker"
                            Layout.fillWidth: true
                            model: App.tasks
                            textRole: "display_name"
                            currentIndex: {
                                for (let index = 0; index < App.tasks.length; index++) {
                                    if (App.tasks[index].id === App.currentTask.id) return index
                                }
                                return App.tasks.length ? 0 : -1
                            }
                            onActivated: App.openTask(App.tasks[currentIndex].id)
                        }
                        Text {
                            visible: App.tasks.length === 0
                            Layout.fillWidth: true
                            text: "لا توجد عمليات تحويل بعد."
                            color: themeColors.muted
                            horizontalAlignment: Text.AlignHCenter
                        }
                        Card {
                            visible: !!App.currentTask.id
                            Layout.fillWidth: true
                            Layout.preferredHeight: taskCardContent.implicitHeight + 60
                            ColumnLayout {
                                id: taskCardContent
                                anchors.fill: parent
                                anchors.margins: 30
                                spacing: 16
                                Item {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 82
                                    Rectangle {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        anchors.top: parent.top
                                        width: Math.min(parent.width, activityRow.implicitWidth + 42)
                                        height: 72
                                        radius: 18
                                        color: taskScreen.conversionActive ? themeColors.violetSoft : (["failed", "cancelled"].includes(App.currentTask.state) ? themeColors.redSoft : (taskScreen.conversionPaused || taskScreen.conversionHasErrors ? themeColors.orangeSoft : themeColors.mintSoft))
                                        RowLayout {
                                            id: activityRow
                                            anchors.centerIn: parent
                                            spacing: 13
                                            BusyIndicator {
                                                objectName: "conversionBusyIndicator"
                                                Layout.preferredWidth: 38
                                                Layout.preferredHeight: 38
                                                visible: taskScreen.conversionActive
                                                running: taskScreen.conversionActive
                                                palette.dark: themeColors.violet
                                            }
                                            Rectangle {
                                                visible: !taskScreen.conversionActive
                                                Layout.preferredWidth: 34
                                                Layout.preferredHeight: 34
                                                radius: 17
                                                color: ["failed", "cancelled"].includes(App.currentTask.state) ? themeColors.red : (taskScreen.conversionPaused || taskScreen.conversionHasErrors ? themeColors.orange : themeColors.mint)
                                                Text { anchors.centerIn: parent; text: App.currentTask.state === "cancelled" ? "×" : (taskScreen.conversionPaused ? "Ⅱ" : (taskScreen.conversionHasErrors ? "!" : "✓")); color: "white"; font.pixelSize: 20; font.bold: true }
                                            }
                                            Text {
                                                Layout.maximumWidth: 560
                                                text: taskScreen.taskStateLabel()
                                                color: themeColors.ink
                                                font.pixelSize: 16
                                                font.weight: Font.Normal
                                                wrapMode: Text.WordWrap
                                            }
                                        }
                                    }
                                }
                                SectionTitle { text: App.currentTask.summary_review_version === 2 ? "مراجعة ترابط الملخصات · " + latinNumber(App.currentTask.total) + " دفعات" : "مهمة تحويل الصفحات " + latinNumber(App.currentTask.start_page) + " إلى " + latinNumber(App.currentTask.end_page) }
                                ProgressBar { Layout.fillWidth: true; from: 0; to: Math.max(1, App.currentTask.total || 1); value: App.currentTask.processed || 0 }
                                Rectangle {
                                    id: currentBatchCard
                                    objectName: "currentBatchCard"
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: Math.max(82, currentBatchContent.implicitHeight + 28)
                                    radius: 13
                                    color: "#f6f7fb"
                                    ColumnLayout {
                                        id: currentBatchContent
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 5
                                        Text {
                                            Layout.fillWidth: true
                                            text: "الدفعة الجارية"
                                            color: themeColors.muted
                                            font.pixelSize: 12
                                            horizontalAlignment: Text.AlignHCenter
                                        }
                                        Text {
                                            objectName: "currentBatchPages"
                                            Layout.fillWidth: true
                                            text: taskScreen.activePagesLabel()
                                            color: themeColors.ink
                                            font.pixelSize: 15
                                            font.weight: Font.Normal
                                            horizontalAlignment: Text.AlignHCenter
                                            wrapMode: Text.WrapAnywhere
                                        }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Repeater {
                                        model: [{label:"حُفظت",value:latinNumber(App.currentTask.completed || 0)},{label:"متبقية",value:latinNumber(App.currentTask.remaining || 0)},{label:"فشلت",value:latinNumber(App.currentTask.failed || 0)}]
                                        delegate: Rectangle {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            height: 82
                                            radius: 13
                                            color: "#f6f7fb"
                                            Column {
                                                anchors.centerIn: parent
                                                spacing: 5
                                                Text { text: modelData.label; color: themeColors.muted; font.pixelSize: 12 }
                                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.value; color: themeColors.ink; font.pixelSize: 22; font.bold: true }
                                            }
                                        }
                                    }
                                }
                                Text { Layout.fillWidth: true; text: App.currentTask.error || "يمكنك التنقل داخل التطبيق. تظل المهمة عاملة، وتحفظ كل نتيجة فور وصولها."; color: App.currentTask.error ? themeColors.red : themeColors.muted; wrapMode: Text.WordWrap }
                                RowLayout { Layout.fillWidth: true
                                    AppButton { visible: App.currentTask.state === "running" && !App.currentTask.control_action; text: "تعليق بعد الدفعة الحالية"; fill: themeColors.orange; onClicked: App.pauseTask() }
                                    AppButton { visible: ["paused","interrupted","failed"].includes(App.currentTask.state); text: "استئناف"; onClicked: App.resumeTask() }
                                    AppButton { visible: App.currentTask.state === "completed_with_errors"; text: "إعادة محاولة الصفحات الفاشلة"; onClicked: App.resumeTask() }
                                    GhostButton {
                                        objectName: "editFailedTaskSettingsButton"
                                        visible: taskScreen.conversionHasErrors
                                        text: "تعديل الإعدادات"
                                        fill: themeColors.violet
                                        foregroundColor: themeColors.violet
                                        onClicked: conversionScreen.prepareFromTask()
                                    }
                                    AppButton { visible: ["queued","running","paused","interrupted","failed","completed_with_errors"].includes(App.currentTask.state) && App.currentTask.control_action !== "cancel"; text: "إلغاء المهمة"; fill: themeColors.red; onClicked: App.cancelTask() }
                                    Item { Layout.fillWidth: true }
                                }
                                RowLayout { Layout.fillWidth: true
                                    AppButton { visible: ["completed","completed_with_errors"].includes(App.currentTask.state) || (App.currentTask.completed || 0) > 0; text: App.currentTask.summary_contract ? "عرض الملخصات" : "مراجعة الصفحة المحوّلة"; fill: themeColors.mint; onClicked: App.openTaskPage() }
                                    GhostButton { text: "العودة إلى الكتاب"; onClicked: App.go("book") }
                                    GhostButton { text: "عرض السجل"; onClicked: App.go("requests") }
                                    Item { Layout.fillWidth: true }
                                }
                            }
                        }
                    }
                }

                // Review
                Item {
                    id: reviewScreen
                    objectName: "reviewScreen"
                    function commitPage(approve) {
                        if (compareLoader.item) compareLoader.item.commitPage(approve)
                        else if (approve) App.approvePage()
                        else App.savePage()
                    }
                    function returnToBook() {
                        commitPage(false)
                        App.go("book")
                    }
                    ColumnLayout { anchors.fill: parent; spacing: 0
                        Rectangle {
                            Layout.fillWidth: true; Layout.preferredHeight: 48; color: themeColors.paper; border.color: themeColors.border
                            RowLayout { anchors.fill: parent; anchors.leftMargin: 11; anchors.rightMargin: 11; spacing: 7
                                GhostButton {
                                    objectName: "reviewBackToBookButton"
                                    text: "العودة إلى الكتاب"
                                    implicitHeight: 34
                                    leftPadding: 12; rightPadding: 12
                                    onClicked: reviewScreen.returnToBook()
                                }
                                Button {
                                    id: reviewBookBreadcrumb
                                    objectName: "reviewBookBreadcrumb"
                                    Layout.maximumWidth: 360
                                    implicitHeight: 34
                                    leftPadding: 10; rightPadding: 10
                                    text: App.currentBook.name || "الكتاب"
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                    onClicked: reviewScreen.returnToBook()
                                    contentItem: Text {
                                        text: reviewBookBreadcrumb.text
                                        color: themeColors.violet
                                        font.family: reviewBookBreadcrumb.font.family
                                        font.pixelSize: reviewBookBreadcrumb.font.pixelSize
                                        font.weight: reviewBookBreadcrumb.font.weight
                                        elide: Text.ElideRight
                                        verticalAlignment: Text.AlignVCenter
                                        font.underline: reviewBookBreadcrumb.hovered || reviewBookBreadcrumb.activeFocus
                                    }
                                    background: Rectangle {
                                        radius: 8
                                        color: reviewBookBreadcrumb.down || reviewBookBreadcrumb.hovered ? themeColors.violetSoft : "transparent"
                                    }
                                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                                }
                                Text { text: "‹"; color: themeColors.muted; font.pixelSize: 18 }
                                Text { text: "المراجعة"; color: themeColors.muted; font.pixelSize: 13 }
                                Item { Layout.fillWidth: true }
                            }
                        }
                        Rectangle {
                            Layout.fillWidth: true; Layout.preferredHeight: 64; color: themeColors.white; border.color: themeColors.border
                            RowLayout { anchors.fill: parent; anchors.margins: 11; spacing: 9
                                GhostButton { objectName: "previousPageButton"; text: "›"; enabled: App.currentPage.number > 1; ToolTip.visible: hovered; ToolTip.text: "الصفحة السابقة"; onClicked: App.openPage(App.currentPage.number - 1) }
                                Text { objectName: "reviewPageIndicator"; text: "صفحة " + (App.currentPage.number ? latinNumber(App.currentPage.number) : "-") + " من " + (App.currentBook.page_count ? latinNumber(App.currentBook.page_count) : "-"); color: themeColors.ink; font.weight: Font.DemiBold }
                                GhostButton { objectName: "nextPageButton"; text: "‹"; enabled: App.currentPage.number < App.currentBook.page_count; ToolTip.visible: hovered; ToolTip.text: "الصفحة التالية"; onClicked: App.openPage(App.currentPage.number + 1) }
                                Item { Layout.fillWidth: true }
                                StatusPill { label: arabicState(App.currentPage.state, App.currentPage.reviewed); tone: stateColor(App.currentPage.state, App.currentPage.reviewed) }
                                GhostButton {
                                    objectName: "pageConversionButton"
                                    text: App.currentPage.state === "done" ? "إعادة تحويل الصفحة" : "تحويل الصفحة"
                                    onClicked: prepareConversion(App.currentPage.number, App.currentPage.number, App.currentPage.state === "done")
                                }
                                GhostButton { text: "حفظ"; onClicked: reviewScreen.commitPage(false) }
                                AppButton { text: "اعتماد الصفحة"; fill: themeColors.mint; onClicked: reviewScreen.commitPage(true) }
                            }
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            color: "#dfe3eb"
                            Loader { id: compareLoader; anchors.fill: parent; sourceComponent: compareComponent }
                        }
                    }
                    Component {
                        id: compareComponent
                        RowLayout {
                            id: compareView
                            anchors.fill: parent
                            anchors.margins: 20
                            spacing: 18
                            LayoutMirroring.enabled: false
                            LayoutMirroring.childrenInherit: false
                            function commitPage(approve) {
                                if (richEditorLoader.item) richEditorLoader.item.commit(approve)
                                else if (approve) App.approvePage()
                                else App.savePage()
                            }

                            Card {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 14
                                    spacing: 10
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text { text: "النص"; color: themeColors.ink; font.pixelSize: 17; font.weight: Font.DemiBold }
                                        Item { Layout.fillWidth: true }
                                        GhostButton {
                                            objectName: "resetPageTextButton"
                                            text: "إعادة النص الأصلي"
                                            implicitHeight: 32
                                            leftPadding: 11; rightPadding: 11
                                            enabled: App.currentPage.can_reset_to_extraction || false
                                            ToolTip.visible: hovered
                                            ToolTip.text: "إلغاء تعديلات هذه الصفحة والعودة إلى آخر تحويل"
                                            onClicked: resetPageDialog.open()
                                        }
                                        Text { text: "يُحفظ تلقائيًا"; color: themeColors.muted; font.pixelSize: 11 }
                                    }
                                    Rectangle { Layout.fillWidth: true; height: 1; color: themeColors.border }
                                    Loader {
                                        id: richEditorLoader
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        active: App.richEditorEnabled
                                        source: "RichEditor.qml"
                                    }
                                    Text {
                                        visible: !App.richEditorEnabled
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        text: "محرر النص معطل في بيئة الاختبار"
                                        color: themeColors.muted
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                }
                            }

                            Card {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 14
                                    spacing: 10
                                    Text { text: "الصفحة الأصلية"; color: themeColors.ink; font.pixelSize: 17; font.weight: Font.DemiBold }
                                    Rectangle { Layout.fillWidth: true; height: 1; color: themeColors.border }
                                    Item {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        Image {
                                            anchors.fill: parent
                                            source: App.currentPage.image_url || ""
                                            fillMode: Image.PreserveAspectFit
                                            asynchronous: true
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Usage
                Item { ScrollView { anchors.fill: parent; contentWidth: availableWidth
                    ColumnLayout { width: Math.min(1050, stack.width-80); x:(stack.width-width)/2; spacing:18
                        Item { Layout.preferredHeight: 20 }
                        RowLayout { Layout.fillWidth:true; SectionTitle { text:"الاستهلاك"; Layout.fillWidth:true } GhostButton{text:"بدء فترة قياس جديدة";onClicked:App.resetUsageMeasurement()} }
                        Text { text:"الأرقام من سجل ورّاق المحلي، وليست كشفًا مباشرًا من Google. يؤخر ورّاق الطلب التالي تلقائيًا كي لا يتجاوز حد الدقيقة."; color:themeColors.muted }
                        RowLayout { Layout.fillWidth:true
                            Repeater { model:[{label:"الطلبات",value:latinNumber(App.usage.requests||0)},{label:"Input",value:latinNumber(App.usage.input||0)},{label:"Output",value:latinNumber(App.usage.output||0)},{label:"Thinking",value:latinNumber(App.usage.thinking||0)},{label:"مجهول",value:latinNumber(App.usage.unknown||0)}]
                                delegate: Card { required property var modelData; Layout.fillWidth:true; height:105; Column { anchors.centerIn:parent; spacing:6; Text{text:modelData.label;color:themeColors.muted;font.pixelSize:12} Text{anchors.horizontalCenter:parent.horizontalCenter;text:modelData.value;color:themeColors.ink;font.pixelSize:24;font.bold:true} } }
                            }
                        }
                        Card { Layout.fillWidth:true; height:180; ColumnLayout { anchors.fill:parent; anchors.margins:22; Text{text:"كيف تُقرأ هذه الأرقام";color:themeColors.ink;font.pixelSize:19;font.bold:true} Text{Layout.fillWidth:true;text:"Input هو إدخال الطلب. Output هو النص الناتج. Thinking يظهر فقط عندما يبلّغ المزود عنه. المحاولات التي لم ترجع بيانات استهلاك تبقى «مجهولة» ولا تُحسب صفرًا.";color:themeColors.muted;wrapMode:Text.WordWrap} Text{Layout.fillWidth:true;text:"يحسب ورّاق كل مفتاح بصورة مستقلة. إذا كانت عدة مفاتيح تابعة لمشروع Google واحد فإنها تشترك فعليًا في حدود Google. يبدأ اليوم عند منتصف الليل بتوقيت المحيط الهادئ.";color:themeColors.muted;wrapMode:Text.WordWrap} } }
                        Text { text:"المتبقي التقديري حسب المفتاح والنموذج"; color:themeColors.ink; font.pixelSize:20; font.bold:true }
                        Repeater { model:App.quotaLimits
                            delegate:Card { required property var modelData; Layout.fillWidth:true; height:96
                                RowLayout { anchors.fill:parent; anchors.margins:16
                                    ColumnLayout{Layout.fillWidth:true;Text{text:modelData.key_name;color:themeColors.ink;font.bold:true}Text{text:modelData.model;color:themeColors.muted;font.pixelSize:12}}
                                    ColumnLayout{Text{text:"اليوم";color:themeColors.muted;font.pixelSize:11}Text{text:latinNumber(modelData.attempts_today)+" / "+latinNumber(modelData.rpd);color:themeColors.ink;font.bold:true}}
                                    ColumnLayout{Text{text:"المتبقي";color:themeColors.muted;font.pixelSize:11}Text{text:latinNumber(modelData.remaining_estimate);color:modelData.remaining_estimate?themeColors.mint:themeColors.red;font.bold:true}}
                                    ColumnLayout{Text{text:"الدقيقة، الحد الآمن";color:themeColors.muted;font.pixelSize:11}Text{text:latinNumber(modelData.requests_last_minute)+" / "+latinNumber(modelData.safe_rpm);color:themeColors.ink;font.bold:true}}
                                    ColumnLayout{Text{text:"إدخال آخر دقيقة";color:themeColors.muted;font.pixelSize:11}Text{text:latinNumber(modelData.known_input_last_minute)+(modelData.input_partially_known?"+":"")+" / "+latinNumber(modelData.input_tpm);color:themeColors.ink;font.bold:true}}
                                }
                            }
                        }
                    }
                } }

                // Requests
                Item { ScrollView { anchors.fill:parent; contentWidth:availableWidth
                    ColumnLayout { width:Math.min(1120,stack.width-70); x:(stack.width-width)/2; spacing:16
                        Item{Layout.preferredHeight:20} SectionTitle{text:"سجل الطلبات"}
                        Card { Layout.fillWidth:true; Layout.preferredHeight:Math.max(160,requestColumn.implicitHeight+28)
                            ColumnLayout { id:requestColumn; anchors.fill:parent; anchors.margins:14; spacing:5
                                RowLayout { Layout.fillWidth:true; Text{Layout.preferredWidth:95;text:"الصفحة";font.bold:true;color:themeColors.muted} Text{Layout.fillWidth:true;text:"النموذج";font.bold:true;color:themeColors.muted} Text{Layout.preferredWidth:120;text:"الحالة";font.bold:true;color:themeColors.muted} Text{Layout.preferredWidth:100;text:"التوكنات";font.bold:true;color:themeColors.muted} Text{Layout.preferredWidth:180;text:"الوقت";font.bold:true;color:themeColors.muted} }
                                Rectangle{Layout.fillWidth:true;height:1;color:themeColors.border}
                                Repeater { model:App.requests
                                    delegate: ColumnLayout { required property var modelData; Layout.fillWidth:true
                                        RowLayout { Layout.fillWidth:true; Text{Layout.preferredWidth:95;text:modelData.page_label;color:themeColors.ink;elide:Text.ElideRight} Text{Layout.fillWidth:true;text:modelData.model;color:themeColors.ink;elide:Text.ElideRight} StatusPill{Layout.preferredWidth:120;label:modelData.state;tone:modelData.state==="success"?themeColors.mint:themeColors.red} Text{Layout.preferredWidth:100;text:modelData.token_total!==""?latinNumber(modelData.token_total):"غير معروف";color:themeColors.muted} Text{Layout.preferredWidth:180;text:modelData.started_at;color:themeColors.muted;font.pixelSize:11} }
                                        Text { visible:!!modelData.error; Layout.fillWidth:true; text:modelData.error; color:themeColors.red; wrapMode:Text.WordWrap; font.pixelSize:11 }
                                        Rectangle{Layout.fillWidth:true;height:1;color:"#eef0f4"}
                                    }
                                }
                                Text{visible:App.requests.length===0;text:"لا توجد طلبات بعد.";color:themeColors.muted;Layout.alignment:Qt.AlignHCenter;Layout.margins:28}
                            }
                        }
                    }
                } }

                // Settings
                Item { id:settingsScreen; objectName:"settingsScreen"; property int tab:0
                    RowLayout { anchors.fill:parent; anchors.margins:28; spacing:18
                        Card { Layout.preferredWidth:210; Layout.fillHeight:true
                            ColumnLayout { anchors.fill:parent; anchors.margins:12
                                Repeater { model:["مفاتيح Gemini","البرومبتات","التنبيهات","النسخ الاحتياطي"]
                                    delegate: Button { required property string modelData; required property int index; Layout.fillWidth:true; height:46; text:modelData; onClicked:settingsScreen.tab=index; background:Rectangle{radius:10;color:settingsScreen.tab===index?themeColors.violetSoft:"transparent"} contentItem:Text{text:parent.text;color:settingsScreen.tab===index?themeColors.violet:themeColors.ink;verticalAlignment:Text.AlignVCenter;font.weight:settingsScreen.tab===index?Font.DemiBold:Font.Normal} HoverHandler{cursorShape:Qt.PointingHandCursor} }
                                }
                                Item{Layout.fillHeight:true}
                            }
                        }
                        StackLayout { Layout.fillWidth:true; Layout.fillHeight:true; currentIndex:settingsScreen.tab
                            ScrollView { contentWidth:availableWidth; ColumnLayout { width:parent.width; spacing:16
                                SectionTitle{text:"مفاتيح Gemini"} Text{text:"أضف اسمًا واضحًا لكل مفتاح. يُحفظ السر في مخزن كلمات المرور في النظام، ولا يدخل قاعدة البيانات أو سجل الطلبات.";color:themeColors.muted;wrapMode:Text.WordWrap;Layout.fillWidth:true}
                                Card { Layout.fillWidth:true; Layout.preferredHeight:keyForm.implicitHeight+40
                                    GridLayout { id:keyForm; anchors.fill:parent; anchors.margins:20; columns:2
                                        FieldLabel{text:"اسم المفتاح"} AppTextField{id:keyName;Layout.fillWidth:true;placeholderText:"المفتاح الأساسي"}
                                        FieldLabel{text:"مفتاح Gemini"} AppTextField{id:keySecret;Layout.fillWidth:true;echoMode:TextInput.Password;placeholderText:"AIza…"}
                                        Item{} AppButton{text:"حفظ في مخزن النظام";onClicked:{App.createKey(keyName.text,keySecret.text);keySecret.text=""}}
                                    }
                                }
                                Card { Layout.fillWidth:true; Layout.preferredHeight:Math.max(110,keyList.implicitHeight+40)
                                    ColumnLayout { id:keyList; anchors.fill:parent; anchors.margins:20; spacing:8
                                        Repeater {
                                            model: App.keys
                                            delegate: Rectangle {
                                                required property var modelData
                                                Layout.fillWidth: true
                                                height: 58
                                                color: "#f7f8fb"
                                                radius: 10
                                                RowLayout {
                                                    anchors.fill: parent
                                                    anchors.margins: 10
                                                    Text { Layout.fillWidth:true; text:modelData.name; color:themeColors.ink; font.bold:true }
                                                    GhostButton {
                                                        text: "حذف"
                                                        fill: themeColors.red
                                                        foregroundColor: themeColors.red
                                                        onClicked: {
                                                            deleteKeyDialog.keyId = modelData.id
                                                            deleteKeyDialog.keyName = modelData.name
                                                            deleteKeyDialog.open()
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                        Text{visible:App.keys.length===0;text:"لم تُضف مفاتيح بعد.";color:themeColors.muted;Layout.alignment:Qt.AlignHCenter;Layout.margins:18}
                                    }
                                }
                            } }
                            ScrollView { contentWidth:availableWidth; ColumnLayout { width:parent.width; spacing:16
                                SectionTitle{text:"البرومبتات"} Text{text:"يمكنك تعديل أي برومبت وحفظه هنا. مخطط النتيجة يبقى تحت إدارة ورّاق.";color:themeColors.muted}
                                Card{Layout.fillWidth:true;Layout.preferredHeight:260;ColumnLayout{anchors.fill:parent;anchors.margins:18;FieldLabel{text:"نسخة مخصصة جديدة"}AppTextField{id:newPromptName;objectName:"newPromptName";Layout.fillWidth:true;placeholderText:"اسم النسخة"}AppComboBox{id:newPromptMode;Layout.fillWidth:true;model:[{id:"printed",name:"نسخ مطبوع"},{id:"manuscript",name:"نسخ مخطوط"},{id:"translation",name:"ترجمة"},{id:"summary",name:"تلخيص"}];textRole:"name"}AppPromptEditor{id:newPromptText;Layout.fillWidth:true;Layout.fillHeight:true;editorObjectName:"newPromptText";placeholderText:"تعليمات المعالجة"}AppButton{text:"حفظ النسخة";onClicked:App.savePrompt("",newPromptName.text,newPromptMode.model[newPromptMode.currentIndex].id,newPromptText.text)}}}
                                Repeater { model:App.prompts.length; delegate:Card{id:promptCard;required property int index;property var promptData:App.prompts[index];objectName:"promptCard-"+promptData.id;property bool expanded:false;Layout.fillWidth:true;Layout.preferredHeight:promptForm.implicitHeight+20
                                    ColumnLayout{id:promptForm;anchors.fill:parent;anchors.margins:10;spacing:8
                                        FieldLabel{text:promptData.name+(promptData.is_default?"، افتراضي":"")}
                                        AppPromptEditor{id:promptInstructions;objectName:"promptScroll-"+promptData.id;editorObjectName:"promptInstructions-"+promptData.id;Layout.fillWidth:true;Layout.preferredHeight:promptCard.expanded?220:36;text:promptData.instructions;readOnly:!promptCard.expanded}
                                        RowLayout{Layout.fillWidth:true
                                            GhostButton{text:promptCard.expanded?"إخفاء التفاصيل":"تعديل البرومبت";onClicked:promptCard.expanded=!promptCard.expanded}
                                            Item{Layout.fillWidth:true}
                                            AppButton{objectName:"savePrompt-"+promptData.id;visible:promptCard.expanded;text:"حفظ التعديلات";enabled:promptInstructions.text.trim().length>0;onClicked:App.savePrompt(promptData.id,promptData.name,promptData.mode,promptInstructions.text)}
                                        }
                                    }
                                } }
                            } }
                            ColumnLayout {
                                spacing: 16
                                SectionTitle { text: "التنبيهات" }
                                Text {
                                    Layout.fillWidth: true
                                    text: "يمكن لورّاق تشغيل صوت من نظام التشغيل عند اكتمال التحويل أو فشله أو إلغائه. لا تُنزّل أصوات ولا تُضاف ملفات صوتية إلى التطبيق."
                                    color: themeColors.muted
                                    wrapMode: Text.WordWrap
                                }
                                Card {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: notificationSoundForm.implicitHeight + 40
                                    ColumnLayout {
                                        id: notificationSoundForm
                                        anchors.fill: parent
                                        anchors.margins: 20
                                        spacing: 16
                                        RowLayout {
                                            Layout.fillWidth: true
                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 4
                                                FieldLabel { text: "صوت تنبيهات التحويل" }
                                                Text {
                                                    Layout.fillWidth: true
                                                    text: "يشمل الاكتمال مع وجود صفحات تحتاج إعادة المحاولة."
                                                    color: themeColors.muted
                                                    font.pixelSize: 12
                                                    wrapMode: Text.WordWrap
                                                }
                                            }
                                            Switch {
                                                objectName: "notificationSoundSwitch"
                                                checked: App.notificationSoundEnabled
                                                onToggled: App.setNotificationSoundEnabled(checked)
                                            }
                                        }
                                        Rectangle { Layout.fillWidth: true; height: 1; color: themeColors.border }
                                        GridLayout {
                                            Layout.fillWidth: true
                                            columns: 2
                                            columnSpacing: 16
                                            rowSpacing: 10
                                            FieldLabel { text: "الصوت" }
                                            RowLayout {
                                                Layout.fillWidth: true
                                                AppComboBox {
                                                    id: notificationSoundBox
                                                    objectName: "notificationSoundBox"
                                                    Layout.fillWidth: true
                                                    model: App.notificationSounds
                                                    textRole: "name"
                                                    valueRole: "id"
                                                    enabled: App.notificationSoundEnabled
                                                    currentIndex: {
                                                        for (let index = 0; index < App.notificationSounds.length; index++) {
                                                            if (App.notificationSounds[index].id === App.notificationSoundId)
                                                                return index
                                                        }
                                                        return 0
                                                    }
                                                    onActivated: App.setNotificationSound(currentValue)
                                                }
                                                GhostButton {
                                                    objectName: "previewNotificationSoundButton"
                                                    text: "معاينة"
                                                    enabled: App.notificationSoundEnabled
                                                    onClicked: App.previewNotificationSound()
                                                }
                                            }
                                        }
                                    }
                                }
                                Item { Layout.fillHeight: true }
                            }
                            ColumnLayout { spacing:16; SectionTitle{text:"النسخ الاحتياطي"} Text{Layout.fillWidth:true;text:"تتضمن النسخة قاعدة البيانات والنصوص والإعدادات، ولا تتضمن ملفات PDF الأصلية. يحتفظ ورّاق بنسخة أمان تلقائية قبل الاستعادة.";color:themeColors.muted;wrapMode:Text.WordWrap} Card{Layout.fillWidth:true;height:180;Column{anchors.centerIn:parent;spacing:12;AppButton{text:"إنشاء نسخة احتياطية";onClicked:backupSaveDialog.open()}GhostButton{text:"استعادة نسخة";onClicked:backupOpenDialog.open()}}} Item{Layout.fillHeight:true} }
                        }
                    }
                }

                // Export
                Item { ColumnLayout { width:Math.min(820,stack.width-80); anchors.centerIn:parent; spacing:18
                    SectionTitle{text:"تصدير الكتاب"}
                    Text{Layout.fillWidth:true;text:"اختر الصيغة ونطاق الصفحات ومكان الحفظ. ملف HTML يعمل ككتاب تفاعلي مستقل، مع تنقّل مباشر وبحث يعرض رقم الصفحة لكل نتيجة.";color:themeColors.muted;wrapMode:Text.WordWrap}
                    Card { Layout.fillWidth:true; Layout.preferredHeight:exportForm.implicitHeight+50
                        GridLayout { id:exportForm; anchors.fill:parent;anchors.margins:24;columns:2;rowSpacing:13;columnSpacing:16
                            FieldLabel{text:"الصيغة"}AppComboBox{id:exportFormat;objectName:"exportFormat";Layout.fillWidth:true;model:["Word (.docx)", "Markdown (.md)", "HTML تفاعلي (.html)"];onCurrentIndexChanged:exportPath.text=""}
                            FieldLabel{text:"من صفحة"}AppSpinBox{id:exportFrom;Layout.fillWidth:true;from:1;to:App.currentBook.page_count||1;value:1;editable:true}
                            FieldLabel{text:"إلى صفحة"}AppSpinBox{id:exportTo;Layout.fillWidth:true;from:1;to:App.currentBook.page_count||1;value:App.currentBook.page_count||1;editable:true}
                            FieldLabel{text:"الملف"}RowLayout{Layout.fillWidth:true;AppTextField{id:exportPath;objectName:"exportPath";Layout.fillWidth:true;readOnly:true;placeholderText:"اختر مكان الحفظ"}GhostButton{objectName:"chooseExportDestinationButton";text:"اختيار مكان الحفظ";onClicked:chooseExportDestination()}}
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: {
                            const pages = (App.currentBook.pages || []).filter(page => page.number >= exportFrom.value && page.number <= exportTo.value)
                            const reviewed = pages.filter(page => page.state === "done" && page.reviewed).length
                            const unreviewed = pages.filter(page => page.state === "done" && !page.reviewed).length
                            return "داخل النطاق: " + latinNumber(reviewed) + " صفحة معتمدة و" + latinNumber(unreviewed) + " صفحة مولّدة غير معتمدة."
                        }
                        color: themeColors.muted
                        wrapMode: Text.WordWrap
                    }
                    Text { visible: App.exporting; text: "جارٍ إنشاء الملف في الخلفية…"; color: themeColors.violet; font.weight: Font.DemiBold }
                    RowLayout {
                        Layout.fillWidth: true
                        GhostButton { text: "إلغاء"; onClicked: App.go("book") }
                        Item { Layout.fillWidth: true }
                        AppButton {
                            objectName: "prepareExportButton"
                            text: App.exporting ? "جارٍ الإنشاء…" : "متابعة التصدير"
                            foregroundColor: themeColors.white
                            enabled: exportPath.text.length > 0 && !App.exporting
                            onClicked: {
                                const startPage = exportFrom.commitValue()
                                const endPage = exportTo.commitValue()
                                const pages = (App.currentBook.pages || []).filter(page => page.number >= startPage && page.number <= endPage)
                                exportConfirmationDialog.startPage = startPage
                                exportConfirmationDialog.endPage = endPage
                                exportConfirmationDialog.reviewedCount = pages.filter(page => page.state === "done" && page.reviewed).length
                                exportConfirmationDialog.unreviewedCount = pages.filter(page => page.state === "done" && !page.reviewed).length
                                exportConfirmationDialog.ungeneratedCount = pages.filter(page => page.state !== "done").length
                                exportConfirmationDialog.open()
                            }
                        }
                    }
                } }
                SummariesScreen {
                    id: summariesPanel
                    theme: themeColors
                    onSummarizeRequested: {
                        App.go("convert")
                        operationBox.currentIndex = 2
                        promptBox.currentIndex = 0
                    }
                }
            }
        }
    }

    Rectangle {
        objectName: "toastNotification"
        visible: App.toast.length > 0
        LayoutMirroring.enabled: false
        LayoutMirroring.childrenInherit: false
        anchors.right: parent.right
        anchors.rightMargin: 24
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        width: Math.min(680, parent.width - 48, toastText.implicitWidth + 70)
        height: Math.max(52, toastText.implicitHeight + 24)
        radius: 14
        color: themeColors.ink
        z: 100
        RowLayout { anchors.fill: parent; anchors.margins: 12
            Text { id: toastText; Layout.fillWidth: true; text: App.toast; color: "white"; wrapMode: Text.WordWrap }
            Button { text: "إغلاق"; onClicked: App.clearToast(); background: null; contentItem: Text{text:parent.text;color:"white";font.bold:true} HoverHandler{cursorShape:Qt.PointingHandCursor} }
        }
    }
}

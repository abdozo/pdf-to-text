import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    id: screen
    objectName: "summariesScreen"
    required property var theme
    signal summarizeRequested()
    property var selectedIds: []
    property string selectionBook: ""
    property string groupId: "original"
    property var exportIds: []
    property bool settingsExpanded: false
    readonly property var groups: {
        const options = [{id: "original", name: "الملخصات الأصلية"}]
        const seen = {}
        App.summaries.forEach(record => {
            if (!record.input_ids.length) return
            if (!seen[record.task_id]) {
                seen[record.task_id] = {id: record.task_id,
                    name: (record.review_unit !== null ? "مراجعة ترابط" : "مراجعة مجمعة سابقة") + " · " + record.created_at.slice(0,16).replace("T", " ")}
                options.push(seen[record.task_id])
            }
        })
        return options
    }
    readonly property var visibleSummaries: App.summaries.filter(record => groupId === "original" ? !record.input_ids.length : record.task_id === groupId)
    readonly property var quadrantNames: ["التلخيص الاستيعابي", "الفلسفة والفوائد والدرر العلمية", "النقد المنهجي والاستشكالات", "التوظيف العملي والتوصيات"]
    readonly property var quadrantKeys: ["understanding", "insights", "critique", "applications"]
    LayoutMirroring.enabled: false
    LayoutMirroring.childrenInherit: true

    function toggle(id, checked) {
        selectedIds = checked ? selectedIds.concat([id]) : selectedIds.filter(value => value !== id)
    }
    function prepareReview(task) {
        App.openSummaries(task.book_id)
        const ids = JSON.parse(task.summary_input_ids)
        if (ids.length) App.selectSummary(ids[0])
        selectedIds = ids
        settingsExpanded = true
        reviewBatchSize.value = task.review_batch_size || 1
        reviewKey.currentIndex = App.keys.findIndex(key => key.id === task.key_id)
        const modelIndex = reviewModel.model.findIndex(model => model.id === task.model)
        if (modelIndex >= 0) reviewModel.currentIndex = modelIndex
    }
    Connections {
        target: App
        function onStateChanged() {
            if (screen.selectionBook !== (App.currentBook.id || "")) {
                screen.selectedIds = []
                screen.selectionBook = App.currentBook.id || ""
            }
            const current = App.currentSummary
            const wanted = current.id && current.input_ids.length ? current.task_id : "original"
            if (screen.groupId !== wanted) {
                screen.groupId = wanted
                screen.selectedIds = []
            }
        }
    }
    component Action: Button {
        id: action
        palette.button: screen.theme.violet
        palette.buttonText: "white"
        font.pixelSize: 13
        background: Rectangle {
            implicitWidth: 100; implicitHeight: 38; radius: 8
            color: !action.enabled ? screen.theme.border : action.down ? "#4935b0" : screen.theme.violet
            border.color: action.activeFocus ? screen.theme.ink : "transparent"
            border.width: 2
        }
        HoverHandler { cursorShape: Qt.PointingHandCursor }
    }
    component SummaryComboBox: ComboBox {
        id: combo
        popup.objectName: combo.objectName + "Popup"
        palette.text: screen.theme.ink
        palette.buttonText: screen.theme.ink
        palette.highlightedText: screen.theme.ink
        palette.highlight: screen.theme.violetSoft
        palette.base: screen.theme.white
        palette.button: screen.theme.white
        delegate: ItemDelegate {
            id: option
            required property var modelData
            required property int index
            objectName: combo.objectName + "Option" + index
            width: combo.width
            text: combo.textRole ? modelData[combo.textRole] : modelData
            highlighted: combo.highlightedIndex === index
            contentItem: Text {
                text: option.text
                color: screen.theme.ink
                font: combo.font
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignRight
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                color: option.highlighted || option.hovered ? screen.theme.violetSoft : screen.theme.white
            }
        }
    }

    Dialog {
        id: deleteReviewDialog
        objectName: "deleteSummaryReviewDialog"
        property var summaryIds: []
        property bool wholeList: false
        title: wholeList ? "حذف القائمة كاملة؟" : "حذف الملخصات المحددة؟"
        modal: true
        anchors.centerIn: parent
        width: Math.min(screen.width - 40, 440)
        height: 270
        contentItem: Caption {
            text: "سيُحذف " + deleteReviewDialog.summaryIds.length + " ملخصًا من القائمة المعروضة. تبقى الملخصات الأخرى وملف PDF وسجل الاستهلاك. سيُلغى استئناف المهام المتوقفة التي أنتجت المحدد أو تعتمد عليه، مع إبقاء نتائجها الأخرى. لا يمكن التراجع عن الحذف."
        }
        footer: DialogButtonBox {
            Button { text: "إلغاء"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            Button { objectName: "confirmDeleteSummaryReview"; text: "تأكيد الحذف"; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
        }
        onAccepted: {
            screen.selectedIds = []
            App.deleteSummaries(JSON.stringify(summaryIds))
        }
    }

    component MiniAction: ToolButton {
        id: tool
        font.pixelSize: 11
        padding: 5
        implicitHeight: 32
        contentItem: Text {
            text: tool.text; font: tool.font
            color: tool.enabled ? screen.theme.ink : screen.theme.muted
            opacity: tool.enabled ? 1 : 0.55
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: 6
            color: tool.hovered || tool.down ? screen.theme.violetSoft : "transparent"
            border.color: tool.activeFocus ? screen.theme.violet : "transparent"
        }
        ToolTip.visible: hovered
        ToolTip.text: Accessible.name || text
        HoverHandler { cursorShape: Qt.PointingHandCursor }
    }

    component Caption: Text {
        color: screen.theme.muted
        font.pixelSize: 13
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignRight
        textFormat: Text.PlainText
    }

    FileDialog {
        id: saveDialog
        title: "تصدير الملخصات المختارة"
        fileMode: FileDialog.SaveFile
        defaultSuffix: formatBox.currentIndex === 0 ? "html" : formatBox.currentIndex === 1 ? "md" : "docx"
        nameFilters: formatBox.currentIndex === 0 ? ["HTML (*.html)"] : formatBox.currentIndex === 1 ? ["Markdown (*.md)"] : ["Word (*.docx)"]
        onAccepted: App.exportSummaries(selectedFile.toString(), JSON.stringify(screen.exportIds))
    }

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 20; spacing: 14
        RowLayout {
            Layout.fillWidth: true; layoutDirection: Qt.RightToLeft
            Text { text: "الملخصات"; color: screen.theme.ink; font.pixelSize: 26; font.bold: true }
            SummaryComboBox {
                id: bookBox
                objectName: "summaryBookBox"
                Layout.preferredWidth: 260
                model: App.books; textRole: "name"
                currentIndex: App.books.findIndex(book => book.id === App.currentBook.id)
                onActivated: App.openSummaries(model[currentIndex].id)
                HoverHandler { cursorShape: Qt.PointingHandCursor }
            }
            Item { Layout.fillWidth: true }
            Action { text: "تلخيص صفحات"; onClicked: screen.summarizeRequested() }
        }

        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            layoutDirection: Qt.RightToLeft; spacing: 16
            Rectangle {
                Layout.preferredWidth: 290; Layout.fillHeight: true
                color: screen.theme.white; radius: 12; border.color: screen.theme.border
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 14; spacing: 10
                    SummaryComboBox {
                        objectName: "summarySeriesBox"
                        Layout.fillWidth: true; model: screen.groups; textRole: "name"
                        currentIndex: screen.groups.findIndex(group => group.id === screen.groupId)
                        onActivated: {
                            const id = model[currentIndex].id
                            const record = App.summaries.find(record => id === "original" ? !record.input_ids.length : record.task_id === id)
                            screen.selectedIds = []
                            App.selectSummary(record ? record.id : "")
                        }
                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                    }
                    RowLayout {
                        Layout.fillWidth: true; layoutDirection: Qt.RightToLeft; spacing: 2
                        MiniAction { objectName: "selectAllSummariesButton"; text: "☑ الكل"; Accessible.name: "تحديد الكل"; enabled: screen.visibleSummaries.length > 0; onClicked: screen.selectedIds = screen.visibleSummaries.map(record => record.id) }
                        MiniAction { text: "☐ إلغاء"; Accessible.name: "مسح التحديد"; enabled: screen.selectedIds.length > 0; onClicked: screen.selectedIds = [] }
                        MiniAction {
                            objectName: "deleteSelectedSummariesButton"
                            text: "× المحدد"; Accessible.name: "حذف المحدد"
                            enabled: screen.selectedIds.length > 0
                            onClicked: {
                                deleteReviewDialog.summaryIds = screen.selectedIds.slice()
                                deleteReviewDialog.wholeList = false
                                deleteReviewDialog.open()
                            }
                        }
                        MiniAction {
                            objectName: "deleteSummaryReviewButton"
                            text: "× القائمة"; Accessible.name: "حذف القائمة كاملة"
                            enabled: screen.visibleSummaries.length > 0
                            onClicked: {
                                deleteReviewDialog.summaryIds = screen.visibleSummaries.map(record => record.id)
                                deleteReviewDialog.wholeList = true
                                deleteReviewDialog.open()
                            }
                        }
                    }
                    ScrollView {
                        objectName: "summaryEntriesList"
                        Layout.minimumHeight: 120
                        Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth
                        ColumnLayout {
                            width: parent.width; spacing: 6
                            Repeater {
                                model: screen.visibleSummaries
                                delegate: Rectangle {
                                    required property var modelData
                                    Layout.fillWidth: true; implicitHeight: entryRow.implicitHeight + 14
                                    radius: 8; color: App.currentSummary.id === modelData.id ? screen.theme.violetSoft : screen.theme.paper
                                    RowLayout {
                                        id: entryRow
                                        anchors.fill: parent; anchors.margins: 7; layoutDirection: Qt.RightToLeft
                                        CheckBox {
                                            checked: screen.selectedIds.includes(modelData.id)
                                            onToggled: screen.toggle(modelData.id, checked)
                                            Accessible.name: "تحديد " + modelData.title
                                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                                        }
                                        Button {
                                            Layout.fillWidth: true
                                            background: Item {}
                                            contentItem: ColumnLayout {
                                                Caption { Layout.fillWidth: true; text: modelData.title; color: screen.theme.ink; font.bold: true }
                                                Caption { Layout.fillWidth: true; text: modelData.kind + " · PDF " + modelData.start_page + "–" + modelData.end_page + " · " + modelData.document.sheets.length + " ورقة"; font.pixelSize: 11 }
                                            }
                                            onClicked: App.selectSummary(modelData.id)
                                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                                        }
                                    }
                                }
                            }
                            Caption { Layout.fillWidth: true; visible: !screen.visibleSummaries.length; text: "لا توجد ملخصات في هذه السلسلة. اختر «تلخيص صفحات» للبدء." }
                        }
                    }
                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: screen.theme.border }
                    MiniAction {
                        objectName: "summarySettingsToggle"
                        Layout.fillWidth: true
                        text: (screen.settingsExpanded ? "▾ " : "▸ ") + "إعدادات المراجعة"
                        checkable: true; checked: screen.settingsExpanded
                        onClicked: screen.settingsExpanded = !screen.settingsExpanded
                    }
                    ColumnLayout {
                        objectName: "summarySettingsPanel"
                        Layout.fillWidth: true
                        visible: screen.settingsExpanded
                        spacing: 6
                    RowLayout {
                        Layout.fillWidth: true; layoutDirection: Qt.RightToLeft
                        Caption { Layout.fillWidth: true; text: "ملخصات في الاستعلام" }
                        SpinBox {
                            id: reviewBatchSize
                            objectName: "summaryReviewBatchSize"
                            from: 1; to: 9999; value: 3; editable: true
                            Accessible.name: "عدد الملخصات المستهدفة في كل استعلام مراجعة"
                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                        }
                    }
                    SummaryComboBox {
                        id: reviewKey
                        objectName: "summaryReviewKey"
                        Layout.fillWidth: true; model: App.keys; textRole: "name"
                        Accessible.name: "مفتاح Gemini للمراجعة"
                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                    }
                    SummaryComboBox {
                        id: reviewModel
                        objectName: "summaryReviewModel"
                        Layout.fillWidth: true
                        model: App.models.length ? App.models : [{id:"gemini-3.5-flash-lite",label:"Gemini 3.5 Flash Lite"}]
                        textRole: "label"
                        Accessible.name: "نموذج مراجعة الملخصات"
                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                    }
                    MiniAction { text: "↻ تحديث النماذج"; enabled: reviewKey.currentIndex >= 0 && !App.busy; onClicked: App.refreshModels(reviewKey.model[reviewKey.currentIndex].id) }
                    }
                    Action {
                        objectName: "reviewSummariesButton"
                        Layout.fillWidth: true; text: "مراجعة المحدد (" + screen.selectedIds.length + ")"
                        enabled: screen.selectedIds.length > 0 && reviewKey.currentIndex >= 0 && reviewModel.currentIndex >= 0
                        onClicked: {
                            const entered = Number.fromLocaleString(reviewBatchSize.locale, reviewBatchSize.contentItem.text)
                            if (Number.isFinite(entered)) reviewBatchSize.value = Math.max(reviewBatchSize.from, Math.min(reviewBatchSize.to, Math.round(entered)))
                            App.reviewSummaries(JSON.stringify({ids: screen.selectedIds, key_id: reviewKey.model[reviewKey.currentIndex].id, model: reviewModel.model[reviewModel.currentIndex].id, review_batch_size: reviewBatchSize.value}))
                        }
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: 10
                RowLayout {
                    Layout.fillWidth: true; layoutDirection: Qt.RightToLeft
                    Caption { Layout.fillWidth: true; text: App.currentSummary.id ? App.currentSummary.kind + " · " + App.currentSummary.source_pages.length + " صفحة مصدر" : "اختر ملخصًا لعرضه" }
                    SummaryComboBox { id: formatBox; model: ["HTML", "Markdown", "Word"]; HoverHandler { cursorShape: Qt.PointingHandCursor } }
                    Action {
                        objectName: "exportSelectedSummariesButton"
                        text: screen.selectedIds.length ? "تصدير المحدد (" + screen.selectedIds.length + ")" : "تصدير المعروض"
                        enabled: screen.selectedIds.length > 0 || !!App.currentSummary.id
                        onClicked: {
                            screen.exportIds = screen.selectedIds.length ? screen.selectedIds.slice() : [App.currentSummary.id]
                            saveDialog.open()
                        }
                    }
                }
                Caption {
                    Layout.fillWidth: true
                    visible: !!App.currentSummary.style_warning
                    text: App.currentSummary.style_warning || ""
                }
                ScrollView {
                    id: summaryScroll
                    objectName: "summaryScroll"
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth
                    ColumnLayout {
                        width: summaryScroll.availableWidth; spacing: 22
                        Repeater {
                            model: App.currentSummary.document ? App.currentSummary.document.sheets : []
                            delegate: ColumnLayout {
                                id: sheet
                                required property var modelData
                                Layout.fillWidth: true; spacing: 10
                                Text { Layout.fillWidth: true; text: sheet.modelData.title; textFormat: Text.PlainText; font.family: "Noto Naskh Arabic"; font.pixelSize: 24; font.bold: true; color: screen.theme.ink; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignRight }
                                GridLayout {
                                    objectName: "summaryQuadrantGrid"
                                    Layout.fillWidth: true; columns: 2; layoutDirection: Qt.RightToLeft
                                    columnSpacing: 0; rowSpacing: 0; uniformCellWidths: true
                                    Repeater {
                                        model: 4
                                        delegate: Rectangle {
                                            required property int index
                                            objectName: "summaryQuadrant" + index
                                            Layout.fillWidth: true; Layout.fillHeight: true
                                            Layout.minimumWidth: 0
                                            implicitHeight: quadrantContent.implicitHeight + 32
                                            color: screen.theme.white; border.color: screen.theme.border
                                            ColumnLayout {
                                                id: quadrantContent
                                                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 16; spacing: 12
                                                Text { Layout.fillWidth: true; text: screen.quadrantNames[index]; font.pixelSize: 17; font.bold: true; color: screen.theme.violet; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignRight }
                                                Repeater {
                                                    model: sheet.modelData[screen.quadrantKeys[index]]
                                                    delegate: ColumnLayout {
                                                        required property var modelData
                                                        Layout.fillWidth: true; spacing: 4
                                                        Caption { Layout.fillWidth: true; text: modelData.label; color: screen.theme.ink; font.bold: true }
                                                        Text { Layout.fillWidth: true; text: modelData.text; textFormat: Text.PlainText; font.family: "Noto Naskh Arabic"; font.pixelSize: 18; color: screen.theme.ink; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignRight }
                                                        Text {
                                                            Layout.fillWidth: true; textFormat: Text.RichText
                                                            text: modelData.pdf_pages.map(page => '<a href="' + page + '">[PDF ص ' + page + ']</a>').join(' ')
                                                            linkColor: screen.theme.violet; font.pixelSize: 12
                                                            wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignRight
                                                            onLinkActivated: link => App.openSummarySource(Number(link))
                                                            HoverHandler { cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

import QtQuick
import QtQuick.Layouts
import QtWebChannel
import QtWebEngine

Item {
    id: root

    function commit(approve) {
        const bookId = App.currentBook.id
        const pageNumber = App.currentPage.number
        if (!pageRichTextEditor.editorReady) {
            if (approve) App.approvePage()
            else App.savePage()
            return
        }
        pageRichTextEditor.runJavaScript("window.waraqGetContent()", function(serialized) {
            const content = JSON.parse(serialized || "{}")
            App.commitPageEditorContent(
                bookId,
                pageNumber,
                content.format || "html",
                content.markdown || "",
                content.html || "",
                approve
            )
        })
    }

    WebChannel {
        id: editorChannel
        registeredObjects: [editorHost]
    }

    QtObject {
        id: editorHost
        WebChannel.id: "editorHost"

        function ready() {
            pageRichTextEditor.editorReady = true
            pageRichTextEditor.loadPage()
        }

        function contentChanged(format, markdown, html) {
            App.updatePageEditorContent(format, markdown, html)
        }

        function copyMarkdown(markdown) {
            App.copyMarkdown(markdown)
        }
    }

    WebEngineView {
        id: pageRichTextEditor
        objectName: "pageRichTextEditor"
        property bool editorReady: false
        property real editorScrollTop: 0
        property real editorMaximumScrollTop: 0
        anchors.fill: parent
        url: Qt.resolvedUrl("../editor/editor.html")
        webChannel: editorChannel
        backgroundColor: "#ffffff"

        function loadPage() {
            if (!editorReady) return
            if (App.currentPage.content_format === "markdown") {
                runJavaScript(
                    "window.waraqSetMarkdown("
                    + JSON.stringify(App.currentPage.content_markdown || "")
                    + ","
                    + JSON.stringify(App.currentPage.content_html || "")
                    + ","
                    + JSON.stringify(App.currentPage.text_direction || "rtl")
                    + ")"
                )
            } else {
                runJavaScript("window.waraqSetHtml(" + JSON.stringify(App.currentPage.content_html || "")
                    + "," + JSON.stringify(App.currentPage.text_direction || "rtl") + ")")
            }
        }

        function scrollByWheel(pixelDeltaY, angleDeltaY) {
            const deltaY = pixelDeltaY !== 0 ? -pixelDeltaY : -angleDeltaY / 2
            runJavaScript("window.waraqScrollBy(" + JSON.stringify(deltaY) + ")", function(position) {
                if (!position) return
                pageRichTextEditor.editorScrollTop = Number(position.top)
                pageRichTextEditor.editorMaximumScrollTop = Number(position.maximum)
            })
        }

        Connections {
            target: App
            function onPageLoaded() { pageRichTextEditor.loadPage() }
        }
    }

    MouseArea {
        anchors.fill: parent
        z: 1
        acceptedButtons: Qt.NoButton
        onWheel: function(event) {
            pageRichTextEditor.scrollByWheel(event.pixelDelta.y, event.angleDelta.y)
            event.accepted = true
        }
    }
}

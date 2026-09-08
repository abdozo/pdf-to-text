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
        pageRichTextEditor.runJavaScript("window.waraqGetHtml()", function(html) {
            App.commitPageRichText(bookId, pageNumber, html || "", approve)
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

        function contentChanged(html) {
            App.updatePageRichText(html)
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
            runJavaScript("window.waraqSetHtml(" + JSON.stringify(App.currentPage.content_html || "") + ")")
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

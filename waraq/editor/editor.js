import { Editor } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import Subscript from '@tiptap/extension-subscript'
import Superscript from '@tiptap/extension-superscript'
import TextAlign from '@tiptap/extension-text-align'
import { TextStyleKit } from '@tiptap/extension-text-style'
import { EditorState } from '@tiptap/pm/state'

const normalizeSpaces = value => String(value || '').replace(/\u00a0/g, ' ')

const normalizeLegacyHtml = value => {
  const template = document.createElement('template')
  template.innerHTML = normalizeSpaces(value)
  const classStyles = {
    'ql-align-center': ['textAlign', 'center'],
    'ql-align-right': ['textAlign', 'right'],
    'ql-align-justify': ['textAlign', 'justify'],
    'ql-direction-rtl': ['direction', 'rtl'],
    'ql-font-naskh': ['fontFamily', 'Noto Naskh Arabic'],
    'ql-font-arial': ['fontFamily', 'Arial'],
    'ql-font-plex': ['fontFamily', 'IBM Plex Sans Arabic'],
    'ql-size-small': ['fontSize', '13px'],
    'ql-size-large': ['fontSize', '27px'],
    'ql-size-huge': ['fontSize', '45px']
  }
  template.content.querySelectorAll('[class]').forEach(element => {
    Object.entries(classStyles).forEach(([className, [property, setting]]) => {
      if (element.classList.contains(className)) {
        element.style[property] = setting
        element.classList.remove(className)
      }
    })
    if (!element.classList.length) element.removeAttribute('class')
  })
  return template.innerHTML
}

let host = null
let timer = null

const editor = new Editor({
  element: document.querySelector('#editor'),
  extensions: [
    StarterKit.configure({ link: false, code: false, codeBlock: false }),
    Subscript,
    Superscript,
    TextStyleKit,
    TextAlign.configure({
      types: ['heading', 'paragraph'],
      alignments: ['right', 'center', 'justify'],
      defaultAlignment: 'right'
    })
  ],
  content: '<p></p>',
  editorProps: {
    attributes: {
      dir: 'rtl',
      lang: 'ar',
      'aria-label': 'نص الصفحة',
      spellcheck: 'false'
    }
  },
  onUpdate: ({ editor: currentEditor }) => {
    if (!host) return
    clearTimeout(timer)
    timer = setTimeout(() => host.contentChanged(normalizeSpaces(currentEditor.getHTML())), 300)
    updateToolbar()
  },
  onSelectionUpdate: updateToolbar
})

const run = callback => {
  callback(editor.chain().focus()).run()
  updateToolbar()
}

const actions = {
  bold: chain => chain.toggleBold(),
  italic: chain => chain.toggleItalic(),
  underline: chain => chain.toggleUnderline(),
  strike: chain => chain.toggleStrike(),
  blockquote: chain => chain.toggleBlockquote(),
  orderedList: chain => chain.toggleOrderedList(),
  bulletList: chain => chain.toggleBulletList(),
  subscript: chain => chain.toggleSubscript(),
  superscript: chain => chain.toggleSuperscript(),
  clear: chain => chain.unsetAllMarks().clearNodes()
}

document.querySelectorAll('[data-action]').forEach(button => {
  button.addEventListener('click', () => run(actions[button.dataset.action]))
})

const heading = document.querySelector('#heading')
heading.addEventListener('change', () => {
  const level = Number(heading.value)
  run(chain => level ? chain.setHeading({ level }) : chain.setParagraph())
})

const fontFamily = document.querySelector('#font-family')
fontFamily.addEventListener('change', () => {
  run(chain => fontFamily.value ? chain.setFontFamily(fontFamily.value) : chain.unsetFontFamily())
})

const fontSize = document.querySelector('#font-size')
fontSize.addEventListener('change', () => {
  run(chain => fontSize.value ? chain.setFontSize(fontSize.value) : chain.unsetFontSize())
})

const alignment = document.querySelector('#alignment')
alignment.addEventListener('change', () => run(chain => chain.setTextAlign(alignment.value)))

document.querySelector('#text-color').addEventListener('input', event => {
  run(chain => chain.setColor(event.target.value))
})
document.querySelector('#background-color').addEventListener('input', event => {
  run(chain => chain.setBackgroundColor(event.target.value))
})

function updateToolbar() {
  if (!editor) return
  Object.keys(actions).forEach(action => {
    if (action === 'clear') return
    const button = document.querySelector(`[data-action="${action}"]`)
    if (button) button.classList.toggle('active', editor.isActive(action))
  })
  heading.value = [1, 2, 3, 4, 5, 6].find(level => editor.isActive('heading', { level })) || '0'
  const attributes = editor.getAttributes('textStyle')
  fontFamily.value = attributes.fontFamily || ''
  fontSize.value = attributes.fontSize || ''
  alignment.value = ['center', 'justify'].find(value => editor.isActive({ textAlign: value })) || 'right'
}

const publishLayoutMetrics = () => {
  const root = document.querySelector('.tiptap')
  const firstBlock = root && root.firstElementChild
  if (!firstBlock) return
  const range = document.createRange()
  range.selectNodeContents(firstBlock)
  const editorBounds = root.getBoundingClientRect()
  const textBounds = range.getBoundingClientRect()
  document.title = JSON.stringify({
    editorLeft: editorBounds.left,
    editorRight: editorBounds.right,
    textLeft: textBounds.left,
    textRight: textBounds.right,
    hasNonBreakingSpace: editor.getHTML().includes('\u00a0')
  })
}

const resetEditorState = () => {
  editor.view.updateState(EditorState.create({
    schema: editor.schema,
    doc: editor.state.doc,
    plugins: editor.state.plugins
  }))
}

window.waraqSetHtml = html => {
  editor.commands.setContent(normalizeLegacyHtml(html), { emitUpdate: false })
  resetEditorState()
  updateToolbar()
  requestAnimationFrame(() => requestAnimationFrame(publishLayoutMetrics))
}
window.waraqGetHtml = () => normalizeSpaces(editor.getHTML())
window.waraqScrollBy = deltaY => {
  const root = document.querySelector('.tiptap')
  root.scrollTop += Number(deltaY) || 0
  return { top: root.scrollTop, maximum: root.scrollHeight - root.clientHeight }
}

new QWebChannel(qt.webChannelTransport, channel => {
  host = channel.objects.editorHost
  host.ready()
})

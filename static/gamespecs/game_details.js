window.onload = function () {
    const marked_highlighted = new marked.Marked(
        markedHighlight({
            langPrefix: 'hljs language-',
            highlight(code, lang, info) {
            const language = hljs.getLanguage(lang) ? lang : 'plaintext';
            return hljs.highlight(code, { language }).value;
            }
        })
    );

    document.querySelector('.game-docs').innerHTML = 
        marked_highlighted.parse(documentation);
}


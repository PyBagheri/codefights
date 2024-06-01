var dialog;
var dialog_text;
var dialog_desc;

var dialog_yes;
var dialog_no;

var dialog_confirmation_form;


window.addEventListener('load', function() {
    dialog = document.querySelector('.confirmation-dialog');
    dialog_text = document.querySelector('.confirmation-dialog-title');
    dialog_desc = document.querySelector('.confirmation-dialog-description');

    dialog_yes = document.querySelector('.confirmation-dialog .btn-yes');
    dialog_no = document.querySelector('.confirmation-dialog .btn-no');

    dialog_confirmation_form = document.querySelector('.confirmation-dialog .confirmation-form');

    dialog_yes.addEventListener('click', function(event) {
        dialog_confirmation_form.submit();
        hide_confirmation_dialog();
    });

    dialog_no.addEventListener('click', function(event) {
        hide_confirmation_dialog();
    });

    document.querySelectorAll('.post-confirm-dialog-button').forEach((i) => {
        i.addEventListener('click', function(event) {
            show_confirmation_dialog(
                i.getAttribute('data-dialog-title'),
                i.getAttribute('data-dialog-desc'),
                event.target.getAttribute('data-post-url')
            );
        });
    })
})


function show_confirmation_dialog(text, description, confirmation_url) {
    dialog_text.innerHTML = text;
    dialog_desc.innerHTML = description;

    dialog_confirmation_form.setAttribute('action', confirmation_url);

    dialog.classList.add('visible');
}


function hide_confirmation_dialog() {
    dialog.classList.remove('visible');
    dialog_yes.even
}

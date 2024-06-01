document.querySelector('.btn-attend-fight').addEventListener('click', function(event) {
    if (!event.target.classList.contains("enabled")) {
        return;
    }

    if (!document.querySelector('.info-fight-form-code-select-upload').value) return;

    document.querySelector('.info-fight-form-element').submit();
})

var code_upload_input;

function check_attend_button_enabled() {
    if (code_upload_input.value) {
        document.querySelector(".btn-attend-fight").classList.add("enabled");
    } else {
        document.querySelector(".btn-attend-fight").classList.remove("enabled");
    }
}

window.addEventListener('load', function() {
    code_upload_input = document.querySelector('.info-fight-form-code-select-upload');
   code_upload_input.addEventListener('change', check_attend_button_enabled);
})

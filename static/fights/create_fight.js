var player_search_input = document.querySelector('.info-fight-form-players-search');
var player_search_errors = document.querySelector('.info-fight-form-players-search-errors');
var players_list_element = document.querySelector('.info-fight-form-players-list');
var code_upload_input = document.querySelector('.info-fight-form-code-select-upload');


function check_send_invitations_enabled() {
    // +1 for the host.
    if (min_players <= players_list.length+1 && players_list.length+1 <= max_players &&
        code_upload_input.value
    ) {
        document.querySelector(".btn-send-invitations").classList.add("enabled");
    } else {
        document.querySelector(".btn-send-invitations").classList.remove("enabled");
    }
}

code_upload_input.addEventListener('change', check_send_invitations_enabled);


if (typeof players_list === "undefined") {
    var players_list = [];
} else {
    players_list.forEach(username => {
        add_player_username(username);
    });

    check_send_invitations_enabled();
}

function add_player_username(username) {
    let player_element = document.createElement('div');
    let player_delete_element = document.createElement('div');
    let player_username_element = document.createElement('div');

    player_element.classList.add('info-fight-form-player');
    player_delete_element.classList.add('info-fight-form-player-delete');
    player_username_element.classList.add('info-fight-form-player-username');

    let delete_icon = document.createElement('ion-icon');
    delete_icon.setAttribute('name', 'close-outline');
    player_delete_element.appendChild(delete_icon);

    player_username_element.innerHTML = "@" + username;

    player_element.appendChild(player_delete_element);
    player_element.appendChild(player_username_element);

    player_delete_element.addEventListener('click', function(event) {
        players_list.splice(players_list.indexOf(username), 1);
        player_element.remove();

        check_send_invitations_enabled();
    });

    players_list_element.appendChild(player_element);
}

document.querySelector('.info-fight-form-players-add-btn').addEventListener('click', function() {
    let search_text = player_search_input.value;

    if (players_list.includes(search_text)) {
        return;
    }

    var xhr = new XMLHttpRequest();
    xhr.open("POST", "/fights/api/search/player/", true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.setRequestHeader('X-CSRFToken', csrf_token);
    xhr.onreadystatechange = function() {
        if (xhr.readyState == XMLHttpRequest.DONE) {
            if (JSON.parse(xhr.responseText).success) {
                players_list.push(search_text);
                add_player_username(search_text);
                player_search_input.value = '';

                check_send_invitations_enabled();
            } else {
                player_search_errors.innerHTML = "Player does not exist.";
            }
        }
    }
    xhr.send(JSON.stringify({
        username: search_text
    }));
})

player_search_input.addEventListener('input', function () {
    player_search_errors.innerHTML = "";
})

document.querySelector('.btn-send-invitations').addEventListener('click', function(event) {
    if (!event.target.classList.contains("enabled")) {
        return;
    }

    document.querySelector('.info-fight-form-players-list-input').value = JSON.stringify(players_list);

    document.querySelector('.info-fight-form-element').submit();
})

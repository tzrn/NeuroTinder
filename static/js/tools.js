function cookie(name) {
    const cookies = document.cookie.split('; ');
    for (let i = 0; i < cookies.length; i++) {
        const [key, value] = cookies[i].split('=');
        if (key === name) {
            return decodeURIComponent(value);
        }
    }
    return null;
}

function del_cookie(name) {
    document.cookie = `${name}=; max-age=0; path=/;`;
}

function $(id) {
    return document.getElementById(id)
}

function wsconnect(onmsg) {
    ws = new WebSocket("/chatws");
    ws.onopen = () => {
        console.log("соединение установленно")
    };

    ws.onmessage = () => {
        j = JSON.parse(event.data)
        onmsg(j)
    }

    ws.onclose = () => {
        setTimeout(() => {
            console.log("Попытка восстановить соединение...")
            wsconnect(onmsg)
        }, 2000)
    }

    ws.onerror = (err) => {
        ws.close();
    };
}

function notify(header, value) {
    notifs = $('notifs')
    notif = document.createElement("div")
    notif.classList.add("notif")
    notif.innerHTML = `<p><b>${header}</b></p><p>${value}</p>`
    notifs.appendChild(notif)
    notifs.style.display = "block"
    setTimeout(() => {
        notif.remove()
        if (notifs.childElementCount == 0) {
            notifs.style.display = "none"
        }
    }, 5000)
}
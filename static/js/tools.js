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

function msgnotify(data) {
    console.log(data)
    if (data.audio) {
        c = `голосовое сообщение<audio controls>
                    <source src="/static/audio/${data.audio}" type="audio/wav">
                </audio>`
    } else {
        c = data.contents.length > 50 ? data.contents.slice(0, 50) + "..." : data.contents
    }
    notify(`Сообщение от <a href="/chat/${data.from}">${data.from}</a>`, c)
}

function notify(header, value) {
    //notifs = $('notifs')
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
    }, 10000)
}

notifs = document.createElement("div")
notifs.id = "notifs"
document.body.appendChild(notifs)
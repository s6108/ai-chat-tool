from streamlit_js_eval import streamlit_js_eval


def get_device_id():
    device_id = streamlit_js_eval(
        js_expressions="""
        function getCookie(name) {
            const value = `; ${document.cookie}`;
            const parts = value.split(`; ${name}=`);
            if (parts.length === 2) return parts.pop().split(';').shift();
            return null;
        }

        function setCookie(name, value, days) {
            const maxAge = days * 24 * 60 * 60;
            document.cookie = `${name}=${value}; path=/; max-age=${maxAge}; SameSite=Lax`;
        }

        let id = getCookie("megor_device_id");

        if (!id) {
            id = localStorage.getItem("megor_device_id");
        }

        if (!id) {
            id = crypto.randomUUID();
        }

        localStorage.setItem("megor_device_id", id);
        setCookie("megor_device_id", id, 365);

        id;
        """,
        key="get_device_id_v2",
    )

    return device_id


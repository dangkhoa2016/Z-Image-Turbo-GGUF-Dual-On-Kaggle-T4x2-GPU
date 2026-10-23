if P23_ENABLE_OPTIONAL_WEB_APPS:
    assert urllib.request.urlopen("http://127.0.0.1:18789/auth/session",timeout=8).status==200
    studio_url=quick_tunnel("studio",18789)
    print("======================================")
    print("Z-IMAGE STUDIO DEMO")
    print("URL:      ",studio_url+"/studio/")
    print("Username:  studio")
    print("Password: ",cfg["studio_password"])
    print("======================================")
    print("This is a publicly reachable demo login; do not use it for sensitive workloads.")

    from IPython.display import display, Markdown
    display(Markdown(
        "### Z-Image Studio / Studio trực tuyến\n\n"
        "[Open Studio / Mở Studio](" + studio_url + "/studio/)\n\n"
        "**Username / Tài khoản:** `studio` · **Password / Mật khẩu:** `"
        + cfg["studio_password"] + "`\n\n"
        "*Temporary demonstration login / Đăng nhập demo tạm thời.*"))
else:
    print("P23_OPTIONAL_UI_SKIPPED: Studio HTTPS tunnel (enable P23_ENABLE_OPTIONAL_WEB_APPS to run)")

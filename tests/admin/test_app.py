def test_admin_app_creates():
    from spellbook.admin.app import create_admin_app

    app = create_admin_app()
    assert app is not None
    assert app.title == "Spellbook Admin"

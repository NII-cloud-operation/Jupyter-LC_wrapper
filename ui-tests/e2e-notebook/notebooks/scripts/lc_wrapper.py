"""Helper functions for LC Wrapper E2E tests."""


async def ensure_launcher_tab_opened(page):
    """Ensure launcher tab is opened and active."""
    # Check if Launcher tab exists, if not create one
    launcher_tab = page.locator('//*[contains(@class, "lm-TabBar-tabLabel") and text() = "Launcher"]')
    if not await launcher_tab.is_visible():
        # Click the "+" button to open a new launcher
        await page.locator('//*[@data-command="launcher:create"]').click()

    # Click on "Launcher" tab to make sure it's active
    await page.locator('//*[contains(@class, "lm-TabBar-tabLabel") and text() = "Launcher"]').click()


async def get_notebook_panel_ids(page):
    """Get set of all notebook panel IDs."""
    notebook_panels = page.locator('.jp-NotebookPanel')
    count = await notebook_panels.count()
    ids = []
    for i in range(count):
        panel = notebook_panels.nth(i)
        panel_id = await panel.get_attribute('id')
        ids.append(panel_id)
    return set(ids)


def get_file_browser_item_locator(page, filename):
    return page.locator(f'//*[contains(@class, "jp-DirListing-item") and contains(@title, "Name: {filename}")]')


def get_current_tab_closer_locator(page):
    """Get locator for current tab's close button."""
    return page.locator('.jp-mod-current .lm-TabBar-tabCloseIcon')

async def accept_cookies(page):
    selectors = [
        "#onetrust-accept-btn-handler",
        'button:has-text("Accept")'
    ]

    try:
        await page.wait_for_load_state("domcontentloaded")
    except:
        pass

    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=4000)
            await page.click(selector)
            print("Cookies accepted (main page)")
            return
        except:
            pass

        for frame in page.frames:
            try:
                await frame.wait_for_selector(selector, timeout=2000)
                await frame.click(selector)
                print("Cookies accepted (iframe)")
                return
            except:
                pass

    print("Cookie banner not found or already accepted")

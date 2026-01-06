"""
Скрипт для создания репозитория на GitHub с использованием Playwright.
Перед запуском убедитесь, что вы авторизованы в GitHub в браузере.
"""
from __future__ import annotations

import asyncio
from playwright.async_api import async_playwright


async def create_github_repo(
    repo_name: str = "rutube-downloader",
    description: str = "Скрипт для скачивания видео с Rutube с веб-интерфейсом",
    is_private: bool = False,
) -> None:
    """Создает новый репозиторий на GitHub."""
    async with async_playwright() as p:
        # Запускаем браузер (используем существующую сессию, если есть)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Переходим на страницу создания репозитория
            print(f"Переход на страницу создания репозитория...")
            await page.goto("https://github.com/new")

            # Проверяем, авторизованы ли мы
            if "login" in page.url:
                print("⚠️  Требуется авторизация на GitHub")
                print("Пожалуйста, войдите в свой аккаунт GitHub в открывшемся браузере")
                print("После авторизации нажмите Enter для продолжения...")
                input()

            # Ждем загрузки формы создания репозитория
            print("Ожидание загрузки формы...")
            await page.wait_for_selector('input[name="repository[name]"]', timeout=10000)

            # Заполняем название репозитория
            print(f"Ввод названия репозитория: {repo_name}")
            name_input = page.locator('input[name="repository[name]"]')
            await name_input.fill(repo_name)

            # Заполняем описание (если есть поле)
            try:
                description_input = page.locator('input[name="repository[description]"]')
                if await description_input.is_visible():
                    await description_input.fill(description)
                    print(f"Ввод описания: {description}")
            except Exception:
                pass  # Поле описания может отсутствовать

            # Устанавливаем приватность репозитория
            if is_private:
                try:
                    private_radio = page.locator('input[value="private"]')
                    if await private_radio.is_visible():
                        await private_radio.click()
                        print("Установка приватности: Private")
                except Exception:
                    pass

            # Ждем немного перед созданием
            await asyncio.sleep(1)

            # Нажимаем кнопку создания репозитория
            print("Создание репозитория...")
            create_button = page.locator('button:has-text("Create repository")')
            if not await create_button.is_visible():
                # Пробуем альтернативный селектор
                create_button = page.locator('button[data-disable-with="Creating repository…"]')
            
            await create_button.click()

            # Ждем перехода на страницу нового репозитория
            print("Ожидание создания репозитория...")
            await page.wait_for_url(
                lambda url: f"/{repo_name}" in url and "github.com" in url,
                timeout=30000
            )

            repo_url = page.url
            print(f"✅ Репозиторий успешно создан!")
            print(f"URL: {repo_url}")

            # Получаем URL для push
            try:
                # Ищем кнопку "Code" или текст с URL репозитория
                code_button = page.locator('button:has-text("Code")')
                if await code_button.is_visible():
                    await code_button.click()
                    await asyncio.sleep(0.5)
                
                # Пытаемся найти URL репозитория
                git_url = repo_url.replace("https://github.com/", "").replace(".git", "")
                print(f"\nДля загрузки кода выполните:")
                print(f"git remote add origin https://github.com/{git_url}.git")
                print(f"git branch -M main")
                print(f"git push -u origin main")
            except Exception as e:
                print(f"Не удалось получить URL для push: {e}")
                print(f"Репозиторий создан по адресу: {repo_url}")

            # Ждем немного перед закрытием
            print("\nНажмите Enter для закрытия браузера...")
            input()

        except Exception as e:
            print(f"❌ Ошибка при создании репозитория: {e}")
            print("Проверьте, что вы авторизованы на GitHub и форма загрузилась корректно")
            input("Нажмите Enter для закрытия...")

        finally:
            await browser.close()


if __name__ == "__main__":
    # Можно изменить параметры здесь
    asyncio.run(create_github_repo(
        repo_name="rutube-downloader",
        description="Скрипт для скачивания видео с Rutube с веб-интерфейсом на FastAPI и Docker поддержкой",
        is_private=False
    ))


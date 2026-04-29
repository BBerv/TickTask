import os
from groq import Groq

API_KEY = "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"


def test_groq():
    print("--- Тестирование Groq API ---")
    client = Groq(api_key=API_KEY)

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": "Привет! Если ты работаешь, ответь кратко: 'Groq на связи!'"
                }
            ],
            temperature=1,
            max_tokens=1024,
            top_p=1,
            stream=False,  # Ставим False, чтобы получить весь ответ сразу
        )

        answer = completion.choices[0].message.content
        print("✅ ПОДКЛЮЧЕНИЕ УСПЕШНО!")
        print(f"Ответ ИИ: {answer}")

    except Exception as e:
        print("❌ ПРОИЗОШЛА ОШИБКА!")
        if "403" in str(e):
            print("Ошибка 403 (Forbidden): Похоже, ты забыл включить VPN.")
        elif "401" in str(e):
            print("Ошибка 401: Неверный API-ключ.")
        else:
            print(f"Текст ошибки: {e}")


if __name__ == "__main__":
    test_groq()
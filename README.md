

# 📱 Maestro Mobile Automation Framework

This project provides a robust mobile automation suite using **Maestro**, enriched with **Python** and **Allure Reports** to provide deep visibility into test execution steps and results.

## 🚀 Quick Start

1. **Install Maestro:** `curl -Ls "https://get.maestro.mobile.dev" | bash`
2. **Environment Setup:**

# Edit .env with your ENGINEER_ID and SECURITY_TOKEN

```


3. **Run All Tests:**
```bash
npm run regression

```


*This command runs the flows, enriches them with our Python engine, and opens the Allure dashboard.*

---

## 📊 Reporting Excellence

Unlike standard Maestro outputs, this framework uses a custom **Python Enrichment Engine** to:

* **Capture Steps:** Extract every `tapOn`, `assertVisible`, and comment from YAML flows into the report.
* **Visual Evidence:** Automatically attach screenshots on failure for rapid debugging.
* **Metadata Integration:** Display environment details like Device (iPhone 17) and OS version directly on the dashboard.

---

## 🛠 Project Structure

* `.maestro/flows/`: Main automation test files (YAML).
* `scripts/`: Automation triggers and Allure metadata handlers.
* `allure-results/`: Raw test data (processed by Python into enriched JSON).

---

## 🔒 Security

* Credentials are managed via `.env` file.
* **Important:** Never commit your `.env` file. It is already included in `.gitignore`.

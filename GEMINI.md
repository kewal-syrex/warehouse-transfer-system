# GEMINI.md

## Project Overview

This project is a **Warehouse Transfer Planning Tool**, a web-based application designed to optimize inventory transfers between two warehouses located in Burnaby, Canada, and Kentucky, US. The tool is built with a Python FastAPI backend, a simple HTML/JavaScript frontend, and a MySQL database.

The core purpose of this application is to provide intelligent, stockout-corrected transfer recommendations to prevent stockouts and improve inventory efficiency. It replaces a manual, error-prone Excel-based process.

### Main Technologies

*   **Backend:** Python, FastAPI
*   **Frontend:** HTML, JavaScript, DataTables, Bootstrap
*   **Database:** MySQL
*   **Key Python Libraries:** pandas, numpy, sqlalchemy, openpyxl

### Architecture

The project is structured into three main components:

*   `backend/`: Contains the FastAPI application, including API endpoints, business logic for calculations, and database interaction modules.
*   `frontend/`: Contains the user-facing HTML, JavaScript, and CSS files for the dashboard, transfer planning, and data management interfaces.
*   `database/`: Contains the SQL schema for the MySQL database.

## Building and Running

To build and run this project, follow these steps:

1.  **Set up the environment:**
    *   Create and activate a Python virtual environment:
        ```bash
        python -m venv venv
        venv\Scripts\activate
        ```
    *   Install the required dependencies:
        ```bash
        pip install -r requirements.txt
        ```

2.  **Set up the database:**
    *   Ensure you have a running MySQL server.
    *   Create a new database named `warehouse_transfer`.
    *   Import the database schema from `database/schema.sql`.

3.  **Run the application:**
    *   Start the FastAPI server:
        ```bash
        uvicorn backend.main:app --reload --port 8000
        ```

4.  **Access the application:**
    *   **Dashboard:** [http://localhost:8000/static/index.html](http://localhost:8000/static/index.html)
    *   **API Docs:** [http://localhost:8000/api/docs](http://localhost:8000/api/docs)

## Development Conventions

*   **Coding Style:** The Python code is well-documented with docstrings and comments, following a clear and organized structure.
*   **Testing:** The project includes a `performance_test.py` file for testing the performance of the backend. The `docs/TASKS.md` file also mentions a comprehensive testing strategy, including unit, integration, and UI tests.
*   **Contribution:** The project structure suggests a clear separation of concerns, which should be maintained when adding new features. All business logic should be in the `backend/calculations.py` file, and all database interactions should be in the `backend/database.py` file.

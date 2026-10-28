MASTER PROMPT: BUILD A COMPLETE GLOBAL FUEL PRICES & TAXATION ANALYTICS PROJECT

Act as a senior data engineer, SQL developer, data analyst, Tableau dashboard designer, Python/Flask full-stack developer, and technical documentation specialist.

Your task is to build a complete, runnable, well-documented end-to-end data analytics project titled:

Global Fuel Prices, Taxation and Subsidy Trends (2020–2026)

Build the project as a cohesive solution, not as disconnected examples or a theoretical tutorial. Optimize for low token consumption, minimal unnecessary tool usage, code reuse, and successful execution on a local computer.

Do not spend the response explaining what you plan to do. Start by inspecting available files and creating the actual project files wherever your environment permits. If you cannot create files directly, output complete files in a logical order with their exact paths.

1. Project objective

Develop a data analytics platform that analyzes global petrol, diesel, and LPG prices, taxation, subsidies, affordability, regional differences, and economic relationships.

The intended analysis covers:

84 countries.
7 global regions.
The period 2020–2026.
10 core analytical variables.
A target of 27,468 complete analytical records, if the supplied source data supports this.
Geographic comparisons, time-series trends, tax comparisons, subsidy analysis, and economic indicators.

Never claim that synthetic or unverified data is real-world data. If the original dataset is unavailable, generate a clearly labeled synthetic dataset and provide a documented replacement procedure for real data.

2. Three user personas

Design the analytics around these three use cases.

Persona A: Energy Policy Consultant

Needs to compare country-level tax policies, subsidies, fuel prices, affordability, and regional disparities to develop equitable and environmentally responsible policy recommendations.

Persona B: Global Supply Chain Manager

Needs to monitor regional fuel price differences, historical volatility, fuel procurement costs, and price trends to support transportation planning and cost optimization.

Persona C: Energy Economics Researcher

Needs to analyze the relationship between income levels, fuel prices, tax burdens, subsidies, and affordability across countries and regions.

Make the dashboard and report useful for all three personas.

3. Required technology stack

Use the following technologies:

Python 3.11 or a compatible installed Python version.
Pandas and NumPy for data processing.
SQLAlchemy and SQLite as the default local database.
PostgreSQL compatibility where practical, without requiring it for the default setup.
SQL for database queries, aggregation, validation, and analytical views.
Tableau Public or Tableau Desktop for the primary business intelligence dashboards.
Flask for the web application and dashboard integration.
HTML, CSS, JavaScript, and Bootstrap 5 for a responsive frontend.
Plotly for interactive web visualizations and a functional alternative when Tableau embedding is unavailable.
Pytest for basic automated tests.
Scikit-learn only if it is useful for an optional, lightweight forecasting model.

Avoid unnecessary frameworks, dependencies, microservices, containers, paid APIs, and cloud infrastructure.

The entire project must run locally on a normal Windows 10/11 or macOS computer with at least 8 GB RAM.

4. Required project architecture

Implement this data flow:

CSV/Excel/optional external database → Data ingestion and validation → Pandas preprocessing → SQLite database → SQL analytical views and queries → Tableau dashboards and stories → Flask web application → End-user interactive analytics.

The application must remain usable without Tableau Server or paid Tableau Cloud services.

Important Tableau constraint: Tableau workbook files generally require Tableau Desktop or another compatible Tableau authoring environment to create and validate properly. Do not fabricate a working packaged Tableau workbook or claim an untested workbook is functional.

Instead:

Prepare Tableau-ready CSV files and database tables.
Provide a Tableau connection guide and a Tableau workbook specification.
Generate Tableau workbook files programmatically only if a valid, supported method is available.
Provide a practical dashboard implementation using Plotly inside Flask so the web application is functional even without Tableau.
Include optional instructions for embedding a published Tableau dashboard using a configurable URL.
Clearly document which Tableau steps require manual action in Tableau Desktop/Public.
5. Data requirements

Use a real dataset if one is provided.

If no dataset is provided, create a reproducible synthetic dataset with the following characteristics:

84 unique countries.
7 geographic regions.
Dates covering 2020–2026.
Petrol, diesel, and LPG prices.
Fuel taxes and tax rates.
Government subsidies.
Income group and GDP-per-capita indicators.
Currency and unit metadata where applicable.
Country and region identifiers.

Use sensible, internally consistent relationships between fuel prices, taxes, subsidies, income groups, and regions. Add documented assumptions and reproducible random seeds.

Target the stated 27,468 complete records when feasible. Before claiming this record count, validate the actual generated row count and explain the dataset's grain.

Define the grain clearly, such as country × reporting period × fuel type, or another consistent schema. Do not mix incompatible grains in a single fact table.

Create an appropriate data model with:

A fuel-price fact table.
A country dimension.
A date dimension.
A fuel-type dimension.
Optional tax, subsidy, and economic indicator tables if needed.

Avoid unnecessary duplication. Make all join keys explicit.

Include the following ten core analytical variables, with appropriate supporting identifiers:

Country.
Region.
Date or year.
Fuel type.
Retail fuel price.
Fuel tax amount.
Fuel tax rate.
Subsidy amount or rate.
GDP per capita or income group.
Affordability indicator.

Also include supporting metadata such as units, currency, source, and data quality flags.

Document whether prices are nominal or inflation-adjusted. Do not compare currencies without an explicit conversion or normalization method.

6. Data collection and preprocessing

Implement reusable scripts to:

Load CSV and Excel data.
Validate required columns and data types.
Standardize country, region, date, fuel-type, and currency values.
Remove exact duplicate records.
Detect missing, invalid, and extreme values.
Identify impossible negative prices or invalid tax rates.
Handle missing values using documented, field-specific rules.
Preserve raw source files.
Produce cleaned analytical data.
Log rejected rows and validation errors.
Export cleaned data for Tableau.
Generate a data quality report.

Do not silently delete records or replace missing values without documenting the rule.

Provide a configuration file for data paths, database connection settings, and application settings.

7. Database and SQL requirements

Create the database schema and initialization scripts.

Implement:

Table creation and appropriate data types.
Primary keys, foreign keys, constraints, and indexes.
Data loading using transactions.
Duplicate detection.
Null and range validation.
Analytical SQL views.
Queries for country comparisons, regional averages, tax burdens, subsidy effects, year-over-year changes, and fuel volatility.
A database summary showing row counts, unique countries, regions, fuel types, date ranges, and missing values.

Create reusable SQL files in a dedicated directory.

Include example queries and explain their purpose briefly.

The project must be able to recreate the database from the supplied source data or generated dataset with one documented command.

8. Analytical calculations

Implement and document calculations for:

Average fuel price by country, region, year, and fuel type.
Median and maximum fuel prices.
Fuel tax as a percentage of retail price.
Effective tax burden.
Price changes in absolute and percentage terms.
Year-over-year price changes.
Price volatility using standard deviation or coefficient of variation.
Regional price rankings.
Subsidy-to-price ratio.
Fuel affordability relative to GDP per capita or another explicitly defined income measure.
Correlation between fuel prices, taxes, subsidies, and economic indicators.
Country and region comparisons.
Optional forecasting using a simple baseline and a lightweight time-series model.

Avoid misleading causal claims. Correlation does not prove that taxation or subsidies caused a change in fuel prices.

If reliable historical data is unavailable, label forecasts and demonstrations based on synthetic data accordingly. Show forecast uncertainty when the chosen method supports it.

9. Dashboard and visualization requirements

Build at least 10 distinct, meaningful visualizations. Reuse common filtering and formatting logic instead of duplicating code.

Required visualizations:

Global fuel price choropleth map.
Regional average fuel price comparison.
Fuel price trends from 2020–2026.
Petrol, diesel, and LPG comparison.
Country-level fuel price ranking.
Fuel tax rate comparison.
Fuel price versus tax scatter plot.
Subsidy versus retail price analysis.
Income group versus fuel affordability analysis.
Price volatility and optional forecast visualization.

Use appropriate chart types, meaningful titles, labels, units, legends, hover details, and accessible colors.

If geographic visualization is unavailable offline, provide a clear fallback such as a regional comparison chart or country-level ranking.

10. Dashboard design

Create a polished, responsive analytics dashboard with a professional energy-economics theme.

The dashboard must include:

KPI cards for average fuel price, average tax burden, subsidy ratio, and number of countries.
A global overview page.
A regional and country comparison page.
A taxation and subsidy analysis page.
An affordability and economic analysis page.
A trends and forecasting page.
A clear navigation system.
Loading and empty states.
Error handling.
Responsive layouts for desktop, tablet, and mobile.
Tooltips and chart interactions.
Consistent typography, spacing, and chart styling.

Provide a date filter, country filter, region filter, fuel-type filter, and income-group filter.

All relevant charts and KPI cards must update when filters change. Avoid unnecessary database queries by using efficient aggregations and caching only where appropriate.

11. Tableau requirements

Prepare a Tableau-ready data source and provide the following:

Connection instructions for the local database or exported CSV.
Recommended relationships and joins.
A complete list of calculated fields, with Tableau formulas.
Instructions for building all required visualizations.
Dashboard layout specifications.
Filter and parameter configurations.
Dashboard actions and cross-filtering instructions.
Story points and narrative descriptions.
Formatting and performance recommendations.
Instructions for publishing to Tableau Public if desired.
Instructions for embedding a published Tableau visualization into Flask.

Include calculated fields for tax burden, year-over-year change, subsidy ratio, affordability, and other appropriate KPIs.

Use the Tableau interface available in the target environment rather than assuming all features are identical across Tableau versions.

12. Tableau story requirements

Create a story plan with at least five scenes:

Global fuel price landscape.
Regional and country differences.
Taxation and subsidy policies.
Income and affordability relationships.
Trends, forecasting, and policy or procurement implications.

For each scene, specify the question, visualization, filters, key interpretation, and intended audience.

Generate a concise, evidence-based narrative using the available data. Do not invent findings before analyzing the dataset.

13. Flask web integration

Build a working Flask application with:

A home page and project overview.
A global dashboard page.
Regional analysis.
Tax and subsidy analysis.
Affordability analysis.
Trends and forecasting.
A data methodology page.
A data quality summary.
A Tableau integration page with a configurable embed URL.
A documentation page.

Provide API endpoints returning JSON for dashboard data where appropriate.

Use parameterized SQL queries, validate user inputs, handle exceptions, and avoid exposing database credentials or sensitive configuration.

Implement a safe default mode in which Plotly charts work without a published Tableau dashboard.

Do not pretend a Tableau embed is working if no valid published dashboard URL is configured.

14. Performance and testing

Implement automated tests for:

Dataset generation.
Data validation.
Preprocessing.
Database initialization and loading.
Row counts and unique entities.
SQL analytical views.
Calculation correctness.
Flask routes.
Dashboard data endpoints.
Filter behavior.
Empty and invalid input handling.

Measure and report:

Number of source records.
Number of cleaned records.
Number of records inserted into the database.
Number of countries, regions, and fuel types.
Data preparation time where measurable.
Database load time where measurable.
Basic dashboard response performance.
Number of visualizations.
Number of calculated fields.
Number of dashboard filters.
Number of Tableau story scenes.

Do not fabricate benchmark results. Report actual measurements or mark them as pending execution.

Provide a simple performance testing script and recommendations for optimizing larger datasets.

15. Project structure

Create a clean structure similar to the following, adapting it only when necessary:

global-fuel-analytics/ app.py config.py requirements.txt README.md .env.example .gitignore data/ raw/ processed/ exports/ database/ schema.sql views.sql queries.sql src/ data_generator.py ingestion.py preprocessing.py validation.py database.py analytics.py forecasting.py templates/ base.html index.html dashboard.html regional.html taxation.html affordability.html trends.html methodology.html tableau.html static/ css/ js/ tableau/ calculated_fields.md dashboard_specification.md story_specification.md connection_guide.md tests/ docs/ project_report.md data_dictionary.md sql_guide.md tableau_guide.md user_guide.md presentation_script.md scripts/ setup.py run_pipeline.py run_tests.py

Do not create empty placeholder files for the sake of matching this structure. Every included file must have a defined purpose.

16. Documentation and final deliverables

Create a complete README with:

Project overview.
Architecture.
Prerequisites.
Installation.
Virtual environment setup.
Data source configuration.
Database creation.
Data pipeline execution.
Flask startup.
Test execution.
Tableau setup and integration.
Troubleshooting.
Known limitations.

Also provide:

A detailed step-by-step project report.
A data dictionary.
An ER diagram or Mermaid architecture diagram.
SQL documentation.
Tableau dashboard and story instructions.
A user manual.
A project demonstration script suitable for a 5–10 minute recorded video.
A section covering findings, limitations, and recommendations.
Instructions for replacing synthetic data with authentic sources.

Keep documentation concise but complete and consistent with the actual implementation.

17. One-command execution

The goal is a reproducible local setup.

Provide commands equivalent to:

Create and activate a Python virtual environment.
Install dependencies.
Generate or load the data.
Validate and preprocess it.
Create and populate the database.
Export Tableau-ready datasets.
Run automated tests.
Launch Flask.

Where practical, implement a single pipeline command that performs the data-generation or ingestion, preprocessing, validation, database loading, and export stages in the correct order.

Make the commands work on Windows PowerShell and provide macOS/Linux equivalents where they differ.

18. Credit-saving and execution rules

These rules are mandatory.

Prioritize producing a working project over lengthy explanations.
Do not repeat this specification in your response.
Do not ask questions if a sensible default can be chosen safely.
Inspect supplied data files first, if available.
Use synthetic data only when real input data is absent.
Generate reusable code and shared utilities.
Avoid redundant files, excessive comments, unnecessary abstractions, and duplicate implementations.
Avoid installing unnecessary dependencies.
Do not search the web unless an authentic data source or technical compatibility issue genuinely requires it.
Do not generate multiple alternative architectures.
Do not repeatedly rewrite files that already meet requirements.
Do not claim to have executed commands or tests unless they were actually executed.
Fix straightforward errors before declaring completion.
If output or tool limits are encountered, prioritize the runnable core application, data pipeline, database, primary dashboard, and setup instructions.
Summarize optional enhancements instead of implementing them at the expense of core functionality.
Maintain a checklist of completed and pending requirements.
Use sensible defaults and keep the solution self-contained.
Prefer a small number of high-quality, reusable modules to a large collection of unnecessary files.
19. Acceptance criteria

The project is complete when:

The data pipeline can run from a clean setup.
The database is created and populated successfully.
Data quality and row counts are verifiable.
SQL analytical queries return valid results.
The Flask application starts locally.
The main dashboard displays working interactive charts.
Dashboard filters affect the displayed data correctly.
At least 10 distinct visualizations are implemented.
Tableau-ready data and workbook-building instructions are included.
Five Tableau story scenes are documented.
Automated tests are included and their actual execution status is reported.
Documentation and the demonstration script are provided.
Synthetic and authentic data are clearly distinguished.
No essential component is represented by a fake success message or nonfunctional placeholder.
20. Start execution now

Begin by inspecting the available project files and dataset.

Then create the complete project using the most direct, reliable implementation path.

If you have a file-writing and execution environment, write the files, run the pipeline, execute the tests, fix any straightforward errors, and summarize the actual results.

If you are operating in a chat-only environment, provide the project files in a compact, dependency-aware order. Do not dump every file in one enormous response if that risks truncation; prioritize a runnable core and use the available project-editing or artifact features when possible.

At the end, provide only:

What was implemented.
The final project structure.
Exact setup and run commands.
Actual test and data-validation results.
What requires manual Tableau Desktop/Public configuration.
Any remaining limitations.

The final deliverable must be a practical, reproducible end-to-end project, not merely a proposal or a collection of code snippets.
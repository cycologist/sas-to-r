# Basic SAS to R converter

A small, dependency-free Python script that converts common SAS `DATA` steps
and reporting/analysis procedures into runnable R code.

It is meant as a practical starting point, not a complete SAS compiler.
Generated scripts use base R, with one exception: confirmatory factor analysis
uses the `lavaan` package.

## What it can do

The converter reads a SAS program and emits a single, runnable R script. It
covers small, self-contained analysis programs, including:

- **Data preparation:** `DATA` steps with `DATALINES`/`CARDS`, `SET`,
  assignments, row filters, `IF/THEN/ELSE`, `KEEP`, `DROP`, `RENAME`, and
  `LABEL`.
- **Reporting:** sorted and filtered tables, means by class, frequency tables,
  contents listings, and univariate summaries.
- **Correlation and dimension reduction:** Pearson, Spearman, and Kendall
  correlation; principal components with `prcomp()` or a weighted
  eigendecomposition.
- **Regression:** linear regression with `lm()` and binary logistic regression
  with `glm(..., family = binomial())`, including categorical predictors.
- **Categorical analysis:** one- and two-way crosstabs, expected and percentage
  tables, chi-square tests, and Fisher exact tests.
- **Confirmatory factor analysis:** simple `PROC CALIS` `PATH`/`LINEQS` models
  translated to `lavaan::cfa()`.
- **Weights:** optional `WEIGHT` statements translated for the supported
  analysis procedures.

At a glance:

| SAS construct | Generated R |
| --- | --- |
| `DATA`, `SET`, `INPUT`, `DATALINES` | data frame construction |
| `PROC SORT`, `PRINT`, `MEANS` | `order()`, `print()`, `aggregate()` |
| `PROC FREQ ... / CHISQ` | `table()`/`xtabs()`, `chisq.test()` |
| `PROC CORR` | `cor()` or weighted `cov.wt()` |
| `PROC PRINCOMP` | `prcomp()` or weighted `eigen(cov.wt(...))` |
| `PROC REG` | `lm()` |
| `PROC LOGISTIC` | `glm(..., family = binomial())` |
| `PROC CALIS` | `lavaan::cfa()` |

Unsupported statements produce converter warnings, and some leave `TODO`
comments in the generated R code. Review the output before relying on it.

## Files

```text
sas_to_r.py                    converter and command-line interface
create_github_repo.sh          create and push a GitHub repository
.gitignore                     common Python, R, and editor files to ignore
examples/01_data_step.sas      DATA step example
examples/01_data_step.R        generated R version
examples/02_procedures.sas     PROC example
examples/02_procedures.R       generated R version
examples/03_analysis.sas       weighted analysis example
examples/03_analysis.R         generated R version
examples/04_categorical.sas    crosstab and logistic regression example
examples/04_categorical.R      generated R version
```

## Requirements

- Python 3.10 or newer; no third-party Python packages are required.
- R to run the generated analysis scripts.
- `lavaan` only when converting or running a `PROC CALIS` CFA model.

## Quick start

Convert a SAS file (writes `input.R` next to it):

```bash
python3 sas_to_r.py examples/01_data_step.sas
```

Choose the output file:

```bash
python3 sas_to_r.py examples/02_procedures.sas -o examples/02_procedures.R
```

Print the R code instead of writing a file:

```bash
python3 sas_to_r.py examples/01_data_step.sas --stdout
```

Run the generated examples:

```bash
Rscript examples/01_data_step.R
Rscript examples/02_procedures.R
Rscript examples/03_analysis.R   # CFA part needs lavaan
Rscript examples/04_categorical.R
```

Example 1 produces `students` and `students_clean`. Example 2 prints a sorted
employee table, grouped salary statistics, and department frequencies.
Example 3 demonstrates weighted correlation, weighted PCA, weighted linear
regression, and a weighted CFA. Its CFA call requires `lavaan`:

```r
install.packages("lavaan")
```

Example 4 demonstrates a two-way crosstab, expected counts, row percentages,
a chi-square test of independence, and logistic regression with a categorical
predictor.

## Supported SAS subset

### DATA steps

- `DATA`, `SET`, `INPUT`, `DATALINES` / `CARDS`, and `RUN`
- Numeric and character input variables (`name $`)
- Assignment statements
- `IF condition;` row filtering and `WHERE`
- `IF ... THEN ...; ELSE ...;`
- `KEEP`, `DROP`, `RENAME`, and `LABEL`
- SAS comments (`/* ... */` and `* ... ;`)
- Basic expression translation:
  - `and`, `or`, `not`, `eq`, `ne`, `gt`, `lt`, `ge`, `le`
  - `**`, `=`, `^=`, and numeric missing values (`.`)
  - common functions such as `mean`, `sum`, `min`, `max`, `std`, `round`,
    `upcase`, `lowcase`, `substr`, and `trim`

SAS summary functions ignore missing values by default, so the converter adds
small `.sas_*` helpers when needed (for example `.sas_mean`).

### Procedures

- `PROC SORT` (`BY`, `DESCENDING`, `OUT=`, `NODUPKEY`, `NODUPRECS`)
- `PROC PRINT` (`VAR`, `WHERE`, `NOOBS`)
- `PROC MEANS` (`VAR`, `CLASS`)
- `PROC FREQ` (`TABLES`, `WEIGHT`, `CHISQ`, `FISHER`, `EXPECTED`, `ROW`,
  `COL`, `CELL`, one- and two-way tables) -> `table()`/`xtabs()` and
  `chisq.test()`/`fisher.test()`; Pearson tests use `correct = FALSE` to match
  SAS rather than R's 2x2 continuity correction
- `PROC CONTENTS`
- `PROC UNIVARIATE` (`VAR`)
- `PROC CORR` (`VAR`, `WEIGHT`, `SPEARMAN`, `KENDALL`) -> `cor()` or
  weighted `cov.wt()`
- `PROC PRINCOMP` (`VAR`, `COV`, `WEIGHT`) -> `prcomp()` or weighted
  `eigen(cov.wt(...))`
- `PROC REG` (`MODEL`, `NOINT`, `WEIGHT`) -> `lm()`
- `PROC LOGISTIC` (binary `MODEL`, `CLASS`, `WEIGHT`, `EVENT=`, `EXPB`,
  `NOINT`) -> `glm(..., family = binomial())`, with Wald odds-ratio
  confidence intervals for `EXPB`
- `PROC CALIS` with `PATH` or a simple `LINEQS` model -> `lavaan::cfa()`

Optional `WEIGHT` statements are translated for `PROC FREQ`, `PROC CORR`,
`PROC PRINCOMP`, `PROC REG`, `PROC LOGISTIC`, and `PROC CALIS`. The weighted
procedures use, respectively, weighted `xtabs()`, `cov.wt()`, a weighted
covariance/correlation eigendecomposition, `lm(weights = ...)`,
`glm(weights = ...)`, and `lavaan`'s `sampling_weights` argument.

## R packages

Most generated code uses base R. The CFA translation requires `lavaan`:

```r
install.packages("lavaan")
```

## Limitations

Not yet supported:

- SAS macros (`%MACRO`, `%LET`, `%INCLUDE`, ...)
- `PROC SQL`
- `MERGE`, `RETAIN`, arrays, and `DO` loops
- Informats, formats, and date/time literals
- External files (`INFILE`/`FILE`)
- `PROC GLM`, `PROC MIXED`, multinomial/ordinal logistic regression, and other
  advanced procedures
- `PROC CALIS` specifications using `RAM` or `MATRIX`; only simple `PATH` and
  `LINEQS` models are translated
- SAS library semantics (`LIBNAME` is ignored; only the table name is used)

Unsupported statements produce converter warnings. Some also leave a `TODO`
comment in the generated R script so they are easy to find.

## Notes

- SAS dataset names are flattened: `work.students` becomes the R object
  `students`.
- `_LAST_` is resolved when the converter can track the most recent dataset.
- Numeric missing values in `DATALINES` are converted to `NA`.
- `IF/THEN/ELSE` is emitted with `ifelse()`. As in SAS, this is vectorised, but
  unusual type combinations may still need manual review.
- Weighted PCA is computed with a base-R eigendecomposition rather than
  `prcomp()`, so its object shape differs from the unweighted version.
- Weighted correlation and PCA use complete cases for the variables and weight.
- `PROC REG` and `PROC LOGISTIC` formulas are translated from simple
  space-separated `MODEL` terms. Complex model syntax may need manual
  adjustment.
- `PROC LOGISTIC` is translated to binary `glm()`. `EVENT='1'` (or another
  event value) is converted with `I(response == "value")`; `DESCENDING` is
  reported as a warning because the explicit event level is preferred. With
  no `EVENT=`, a numeric response should be coded 0/1; a factor response is
  modeled as the probability of its second level.
- `PROC FREQ` `CHISQ` supports one-way goodness-of-fit and two-way
  independence tests; higher-way tables need a manual model.
- `PROC FREQ` weights are treated as frequency counts via `xtabs()`.
- CFA `PATH` statements map to `lavaan` measurement equations
  (`F1 -> x1 x2` becomes `F1 =~ x1 + x2`). Review the generated model,
  especially for structural paths or `LINEQS`.
- Always inspect generated code and warnings before relying on it.

## Regenerating the examples

```bash
python3 sas_to_r.py examples/01_data_step.sas
python3 sas_to_r.py examples/02_procedures.sas
python3 sas_to_r.py examples/03_analysis.sas
python3 sas_to_r.py examples/04_categorical.sas
```

## Creating a GitHub repository

`create_github_repo.sh` prepares this directory as a Git repository, creates an
initial commit if needed, creates a GitHub repository for the authenticated
GitHub CLI account, adds `origin`, and pushes the current branch.

Prerequisites:

- Git
- [GitHub CLI](https://cli.github.com/) (`gh`)
- Authentication with `gh auth login`
- Git `user.name` and `user.email` configured

Usage:

```bash
chmod +x create_github_repo.sh

./create_github_repo.sh                          # private, uses directory name
./create_github_repo.sh sas-to-r --public        # public repository
./create_github_repo.sh my-user/sas-to-r         # explicit owner
```

Options:

- `--private` creates a private repository (the default).
- `--public` creates a public repository.
- `GIT_BRANCH=main` sets the branch name for a new local repository
  (the default).
- `REPO_DESCRIPTION="..."` overrides the repository description.

The script refuses to continue if the directory is inside another Git
repository, if an `origin` remote already exists, if the GitHub repository
already exists, or if an existing local repository has uncommitted changes.

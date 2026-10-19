# SAS to R converter

A small, dependency-free Python script that converts common SAS `DATA` steps
and selected analysis procedures into runnable R code.

It is meant as a practical starting point, not a complete SAS compiler.
Generated scripts use base R plus the recommended R packages `nlme`, `MASS`,
and `nnet` for mixed, ordinal, and multinomial models. Confirmatory factor
analysis uses `lavaan`.

## What it can do

The converter reads a SAS program and emits a single, runnable R script. It
covers small, self-contained analysis programs, including:

- **Data preparation:** `DATA` steps with `DATALINES`/`CARDS`, `SET`,
  assignments, row filters, `IF/THEN/ELSE`, `KEEP`, `DROP`, `RENAME`, and
  `LABEL`.
- **External files:** local `FILENAME` filerefs, `INFILE` for delimited or
  whitespace-separated input, and `FILE`/`PUT` for simple text or CSV output,
  including `DATA _NULL_` steps that use `FILE` and `PUT`.
- **Reporting:** sorted and filtered tables, means by class, frequency tables,
  contents listings, and univariate summaries.
- **Correlation and dimension reduction:** Pearson, Spearman, and Kendall
  correlation; principal components with `prcomp()` or a weighted
  eigendecomposition.
- **Regression and models:** linear regression, fixed-effects ANOVA/ANCOVA,
  mixed-effects models, generalized linear models, and binary, ordinal, and
  multinomial logistic regression.
- **Hypothesis tests:** one-sample, two-sample, paired, and pairwise t tests;
  Wilcoxon rank-sum and Kruskal-Wallis tests.
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
| `FILENAME`, `INFILE` | `read.table()` |
| `FILE`, `PUT` | `write.table()` |
| `PROC SORT`, `PRINT`, `MEANS` | `order()`, `print()`, `aggregate()` |
| `PROC FREQ ... / CHISQ` | `table()`/`xtabs()`, `chisq.test()` |
| `PROC CORR` | `cor()` or weighted `cov.wt()` |
| `PROC PRINCOMP` | `prcomp()` or weighted `eigen(cov.wt(...))` |
| `PROC REG` | `lm()` |
| `PROC GLM`, `PROC ANOVA` | `lm()` and `anova()` |
| `PROC MIXED` | `nlme::lme()` |
| `PROC TTEST` | `t.test()` or `pairwise.t.test()` |
| `PROC NPAR1WAY` | `wilcox.test()` or `kruskal.test()` |
| `PROC GENMOD` | `glm()` or `MASS::glm.nb()` |
| `PROC LOGISTIC` | `glm()`, `MASS::polr()`, or `nnet::multinom()` |
| `PROC CALIS` | `lavaan::cfa()` |

Unsupported statements produce converter warnings, and some leave `TODO`
comments in the generated R code. Review the output before relying on it.

## Files

```text
sas_to_r.py                         converter and command-line interface
create_github_repo.sh               create and push a GitHub repository
.gitignore                          common Python, R, and editor files to ignore
examples/01_data_step.sas           DATA step example
examples/01_data_step.R             generated R version
examples/02_procedures.sas          PROC example
examples/02_procedures.R            generated R version
examples/03_analysis.sas            weighted analysis example
examples/03_analysis.R              generated R version
examples/04_categorical.sas         crosstab and logistic regression example
examples/04_categorical.R           generated R version
examples/05_advanced.sas            external-file, GLM, MIXED, ordinal and multinomial example
examples/05_advanced.R              generated R version
examples/06_other_procedures.sas    TTEST, NPAR1WAY, ANOVA, and GENMOD example
examples/06_other_procedures.R      generated R version
```

Example 5 writes and then reads `examples/advanced_data.csv`; that generated
data file is ignored by Git.

## Requirements

- Python 3.10 or newer; no third-party Python packages are required.
- R to run the generated analysis scripts.
- The recommended R packages `nlme`, `MASS`, and `nnet` for `PROC MIXED`,
  ordinal logistic regression, and multinomial logistic regression. These are
  normally installed with R, but can be installed explicitly.
- `lavaan` only when converting or running a `PROC CALIS` CFA model.

```r
install.packages(c("nlme", "MASS", "nnet"))
install.packages("lavaan")   # only for PROC CALIS
```

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

Run the generated examples from the project directory:

```bash
Rscript examples/01_data_step.R
Rscript examples/02_procedures.R
Rscript examples/03_analysis.R       # CFA part needs lavaan
Rscript examples/04_categorical.R
Rscript examples/05_advanced.R       # needs nlme, MASS, and nnet
Rscript examples/06_other_procedures.R
```

Example 1 produces `students` and `students_clean`. Example 2 prints a sorted
employee table, grouped salary statistics, and department frequencies. Example
3 demonstrates weighted correlation, weighted PCA, weighted linear regression,
and a weighted CFA. Its CFA call requires `lavaan`:

```r
install.packages("lavaan")
```

Example 4 demonstrates a two-way crosstab, expected counts, row percentages,
a chi-square test of independence, and logistic regression with a categorical
predictor.

Example 5 writes a CSV file with `FILE`/`PUT`, reads it back with `INFILE`,
then fits a weighted fixed-effects model, a random-intercept mixed model, an
ordinal proportional-odds model, and a multinomial logistic model.

Example 6 demonstrates two-sample and paired t tests, rank-based tests,
one-way ANOVA, and a Poisson generalized linear model.

Run example 5 from the project directory, because its external-file paths are
relative to the R working directory.

## Supported SAS subset

### DATA steps

- `DATA`, `SET`, `INPUT`, `DATALINES` / `CARDS`, and `RUN`
- Numeric and character input variables (`name $`)
- `FILENAME` for local file references, and `INFILE` with `DLM=`/`DELIMITER=`,
  `DSD`, `FIRSTOBS=`, `OBS=`, and `MISSOVER`/`TRUNCOVER` (read with `fill`)
- `FILE` with `DLM=`/`DELIMITER=`, `DSD`, and `MOD`, plus simple `PUT`
  variable lists or `PUT _ALL_`
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
- `PROC GLM` and `PROC ANOVA` (`CLASS`, `MODEL`, `MEANS`, `WEIGHT`, `NOINT`)
  -> `lm()` and `anova()`; sequential Type I sums of squares are used
- `PROC MIXED` (`CLASS`, `MODEL`, `RANDOM`, `WEIGHT`, `METHOD=REML|ML`) ->
  `nlme::lme()`; simple random intercepts and slopes are supported
- `PROC TTEST` (`CLASS`, `VAR`, `PAIRED`, `H0=`, `SIDES=`) -> `t.test()` and
  `pairwise.t.test()`
- `PROC NPAR1WAY` (`CLASS`, `VAR`) -> `wilcox.test()` for two groups and
  `kruskal.test()` for more than two
- `PROC GENMOD` (`CLASS`, `MODEL`, `WEIGHT`, `DIST=`, `LINK=`) -> `glm()` for
  common distributions or `MASS::glm.nb()` for negative binomial models
- `PROC LOGISTIC`:
  - binary and event-coded models -> `glm(..., family = binomial())`
  - ordinal models -> `MASS::polr()` with proportional odds
  - multinomial models with `LINK=GLOGIT` -> `nnet::multinom()`
  - supports `CLASS`, `WEIGHT`, `EVENT=`, `EXPB`, `NOINT`, and common links
- `PROC CALIS` with `PATH` or a simple `LINEQS` model -> `lavaan::cfa()`

Optional `WEIGHT` statements are translated for `PROC FREQ`, `PROC CORR`,
`PROC PRINCOMP`, `PROC REG`, `PROC GLM`/`ANOVA`, `PROC MIXED`,
`PROC LOGISTIC`, `PROC GENMOD`, and `PROC CALIS`. The weighted procedures use,
respectively, weighted `xtabs()`, `cov.wt()`, a weighted
covariance/correlation eigendecomposition, `lm(weights = ...)`,
`glm(weights = ...)`, `nlme::lme(weights = ...)`, and `lavaan`'s
`sampling_weights` argument. `PROC MIXED` treats the weight variable as an
inverse-variance weight and uses `weights = ~ I(1 / w)`.

## R packages

Most generated code uses base R. The analysis procedures that need additional
packages use recommended R packages:

```r
install.packages(c("nlme", "MASS", "nnet"))
```

`PROC CALIS` translation requires `lavaan`:

```r
install.packages("lavaan")
```

## Limitations

Not yet supported:

- SAS macros (`%MACRO`, `%LET`, `%INCLUDE`, ...)
- `PROC SQL`
- `MERGE`, `RETAIN`, arrays, and `DO` loops
- Informats, formats, and date/time literals
- External-file features beyond delimited/whitespace input and simple `PUT`
  lists: fixed-width column input, URL/pipe filerefs, and complex `PUT`
  formatting are not translated
- `PROC GLM` options such as `LSMEANS`, `CONTRAST`, `ESTIMATE`, and `TEST`;
  `PROC GLM` uses sequential Type I sums of squares
- `PROC MIXED` repeated-measures covariance structures, `LSMEANS`, and
  complex random-effects specifications; only simple random intercepts and
  slopes are translated
- Stepwise selection, `PROC LOGISTIC` score tests, exact tests, and other
  specialized options
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
- External-file paths are passed to R as written, so they are relative to the
  working directory in which the generated R script is run.
- `INFILE` uses `read.table()` for whitespace-separated or single-character
  delimited files. `FILE` uses `write.table()` and writes no header row.
  `FILE`/`PUT` output is emitted after the DATA step's assignments and before
  `KEEP`/`DROP`/`RENAME`; a `PUT` in the middle of a step is not evaluated at
  that exact point.
- `IF/THEN/ELSE` is emitted with `ifelse()`. As in SAS, this is vectorised, but
  unusual type combinations may still need manual review.
- Weighted PCA is computed with a base-R eigendecomposition rather than
  `prcomp()`, so its object shape differs from the unweighted version.
- Weighted correlation and PCA use complete cases for the variables and weight.
- `PROC REG`, `PROC GLM`, `PROC MIXED`, and `PROC LOGISTIC` formulas are
  translated from simple space-separated `MODEL` terms. Complex model syntax
  may need manual adjustment.
- `CLASS` reference levels follow R defaults. SAS parameterization may differ,
  so coefficient labels and signs can differ even when the fitted model is
  equivalent.
- `PROC GLM` prints both the coefficient summary and an `anova()` table.
  `MEANS` statements produce simple grouped means; multiple-comparison
  adjustments such as Tukey HSD are not reproduced.
- `PROC MIXED` prints the `nlme` model summary and an ANOVA table. The first
  `RANDOM` statement is used; `REPEATED` and unsupported covariance types are
  reported as warnings.
- `PROC TTEST` with two class levels uses `t.test()`. With more than two class
  levels it uses `pairwise.t.test()` without multiplicity adjustment.
- `PROC NPAR1WAY` uses a Wilcoxon rank-sum test for two groups and a
  Kruskal-Wallis test otherwise.
- `PROC LOGISTIC` with `EVENT=` converts the response with
  `I(response == "value")`. Without `EVENT=`, a response with more than two
  levels is fitted as an ordinal model with `MASS::polr()`; a two-level response
  is fitted with `glm()`. `LINK=GLOGIT` selects `nnet::multinom()`.
  `DESCENDING` is reported as a warning because an explicit event level is
  preferred. `NOINT` is honored for binary and multinomial models; `MASS::polr`
  retains its intercepts for ordinal models. The `LOGLOG` link is available
  for ordinal models; the binary branch falls back to logit with a warning.
- `EXPB` produces Wald odds-ratio intervals for binary and ordinal models; for
  multinomial models it prints exponentiated coefficients. For ordinal models,
  threshold parameters are excluded from the odds-ratio table.
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
python3 sas_to_r.py examples/05_advanced.sas
python3 sas_to_r.py examples/06_other_procedures.sas
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

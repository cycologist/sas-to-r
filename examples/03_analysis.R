# Converted from 03_analysis.sas by sas_to_r.py
# R output; review warnings and generated code before use.

# ---- data step: work.survey ----
survey <- read.table(
  text = "1 2.1 3.1 1.9 5.0 1.0\n2 3.4 4.2 2.8 6.3 1.5\n3 1.8 2.6 1.5 4.4 0.8\n4 4.2 5.0 3.7 7.6 1.2\n5 2.9 3.8 2.4 5.8 1.0\n6 5.1 6.2 4.5 8.4 2.0\n7 3.7 4.6 3.1 6.9 1.4\n8 2.5 3.4 2.1 5.3 0.9",
  header = FALSE,
  stringsAsFactors = FALSE,
  comment.char = "",
  colClasses = "numeric"
)
names(survey) <- c("id", "x1", "x2", "x3", "y", "w")

# ---- proc corr: survey ----
corr_data <- survey[complete.cases(survey[, c("x1", "x2", "x3", "y", "w")]), ]
print(round(cov.wt(corr_data[, c("x1", "x2", "x3", "y")], wt = corr_data$w, cor = TRUE)$cor, 3))

# ---- proc princomp: survey ----
pca_data_1 <- survey[complete.cases(survey[, c("x1", "x2", "x3", "w")]), ]
pca_1 <- eigen(stats::cov.wt(pca_data_1[, c("x1", "x2", "x3")], wt = pca_data_1$w, cor = FALSE)$cov)
print(pca_1$values)
print(pca_1$vectors)

# ---- proc reg: survey ----
reg_fit_1 <- stats::lm(y ~ x1 + x2 + x3, data = survey, weights = survey$w)
print(summary(reg_fit_1))

# ---- proc calis: survey ----
# Requires lavaan: install.packages("lavaan")
cfa_model_1 <- '
F1 =~ x1 + x2 + x3 + y
'
cfa_fit_1 <- lavaan::cfa(cfa_model_1, data = survey, sampling_weights = "w")
print(summary(cfa_fit_1, fit_measures = TRUE))

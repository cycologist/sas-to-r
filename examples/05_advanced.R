# Converted from 05_advanced.sas by sas_to_r.py
# R output; review warnings and generated code before use.

# ---- data step: work.long ----
long <- read.table(
  text = "1 A 1 10.2 1 1 2 1\n1 A 2 11.0 1 2 3 2\n1 A 3 11.5 2 2 4 3\n2 A 1 9.8 1 1 2 1\n2 A 2 10.7 2 3 3 2\n2 A 3 11.1 2 3 4 3\n3 A 1 12.0 2 1 3 1\n3 A 2 12.6 2 2 4 2\n3 A 3 13.0 3 2 5 3\n4 A 1 10.5 1 2 2 1\n4 A 2 11.2 1 3 3 2\n4 A 3 11.9 2 3 4 3\n5 B 1 13.1 2 1 4 1\n5 B 2 13.8 3 2 5 2\n5 B 3 14.2 3 2 6 3\n6 B 1 12.7 2 2 4 1\n6 B 2 13.4 2 3 5 2\n6 B 3 14.0 3 3 6 3\n7 B 1 14.3 3 1 5 1\n7 B 2 14.9 3 2 6 2\n7 B 3 15.4 3 3 7 3\n8 B 1 13.5 2 2 4 1\n8 B 2 14.1 2 3 5 2\n8 B 3 14.8 3 3 6 3",
  header = FALSE,
  stringsAsFactors = FALSE,
  comment.char = "",
  colClasses = c("numeric", "character", "numeric", "numeric", "numeric", "numeric", "numeric", "numeric")
)
names(long) <- c("id", "group", "time", "score", "y3", "y4", "count", "w")

# ---- data step: _NULL_ ----
null_data_1 <- long
write.table(
  null_data_1[, names(null_data_1), drop = FALSE],
  file = "examples/advanced_data.csv",
  sep = ",",
  row.names = FALSE,
  col.names = FALSE,
  quote = TRUE,
  na = ".",
  append = FALSE,
  qmethod = "double"
)

# ---- data step: work.long_file ----
long_file <- read.table(
  file = "examples/advanced_data.csv",
  header = FALSE,
  sep = ",",
  quote = "\"",
  stringsAsFactors = FALSE,
  comment.char = "",
  fill = TRUE,
  check.names = FALSE,
  na.strings = c("NA", "."),
  colClasses = c("numeric", "character", "numeric", "numeric", "numeric", "numeric", "numeric", "numeric")
)
names(long_file) <- c("id", "group", "time", "score", "y3", "y4", "count", "w")

# ---- proc glm: long_file ----
glm_fit_1 <- stats::lm(score ~ factor(group) + time + factor(group)*time, data = long_file, weights = long_file$w)
print(summary(glm_fit_1))
print(stats::anova(glm_fit_1))
print(stats::aggregate(score ~ group, data = long_file, FUN = mean, na.rm = TRUE))

# ---- proc mixed: long_file ----
mixed_fit_1 <- nlme::lme(
  fixed = score ~ factor(group) + time + factor(group)*time,
  random = ~ 1 | id,
  data = long_file,
  weights = ~ I(1 / w),
  na.action = stats::na.omit
)
print(summary(mixed_fit_1))
print(stats::anova(mixed_fit_1))

# ---- proc logistic: long_file ----
logit_fit_1_response <- ordered(long_file$y3)
if (nlevels(logit_fit_1_response) > 2L) {
  logit_fit_1 <- MASS::polr(logit_fit_1_response ~ factor(group) + time, data = long_file, Hess = TRUE, method = "logistic", weights = long_file$w)
} else {
  logit_fit_1 <- stats::glm(logit_fit_1_response ~ factor(group) + time, data = long_file, family = stats::binomial(link = "logit"), weights = long_file$w)
}
print(summary(logit_fit_1))
logit_fit_1_coef <- stats::coef(logit_fit_1)
logit_fit_1_coef <- logit_fit_1_coef[!grepl("|", names(logit_fit_1_coef), fixed = TRUE)]
logit_fit_1_se <- sqrt(diag(stats::vcov(logit_fit_1)))
logit_fit_1_se <- logit_fit_1_se[names(logit_fit_1_coef)]
print(exp(cbind(OR = logit_fit_1_coef, `2.5 %` = logit_fit_1_coef - 1.96 * logit_fit_1_se, `97.5 %` = logit_fit_1_coef + 1.96 * logit_fit_1_se)))

# ---- proc logistic: long_file ----
logit_fit_2 <- nnet::multinom(factor(y4) ~ factor(group) + time, data = long_file, weights = long_file$w, Hess = TRUE, trace = FALSE)
print(summary(logit_fit_2))
print(exp(stats::coef(logit_fit_2)))

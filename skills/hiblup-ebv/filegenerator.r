suppressPackageStartupMessages(library(data.table))

parse_args <- function(args) {
  get_arg <- function(flag, default = NULL) {
    idx <- match(flag, args)
    if (is.na(idx) || idx == length(args)) return(default)
    args[[idx + 1]]
  }
  list(
    output = get_arg("--output", "."),
    n_ind = as.integer(get_arg("--n-ind", "60")),
    n_snp = as.integer(get_arg("--n-snp", "80")),
    seed = as.integer(get_arg("--seed", "123"))
  )
}

generate_demo <- function(output_dir = ".", n_ind = 60, n_snp = 80, seed = 123) {
  set.seed(seed)
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  ids <- sprintf("ID%04d", seq_len(n_ind))
  snp_names <- sprintf("SNP%03d", seq_len(n_snp))

  geno_mat <- matrix(sample(0:2, n_ind * n_snp, replace = TRUE, prob = c(0.3, 0.5, 0.2)), nrow = n_ind, ncol = n_snp)
  colnames(geno_mat) <- snp_names
  geno_dt <- as.data.table(geno_mat)
  geno_dt <- cbind(data.table(ID = ids), geno_dt)

  sire <- sample(c(0L, seq_len(max(2L, floor(n_ind / 4)))), n_ind, replace = TRUE)
  dam <- sample(c(0L, seq_len(max(2L, floor(n_ind / 3)))), n_ind, replace = TRUE)

  genetic_signal <- rowSums(geno_mat[, seq_len(min(10, n_snp)), drop = FALSE])
  phe1 <- as.numeric(scale(genetic_signal + rnorm(n_ind, sd = 1.5)))
  phe2 <- as.numeric(scale(genetic_signal * 0.7 + rnorm(n_ind, sd = 2.0)))

  phe_dt <- data.table(
    ID = ids,
    sire = sire,
    dam = dam,
    phe1 = phe1,
    phe2 = phe2,
    FamilyID = paste0("F", sprintf("%03d", sample(seq_len(max(3L, floor(n_ind / 2))), n_ind, replace = TRUE)))
  )

  ref_n <- max(10L, floor(n_ind * 0.5))
  ref_id <- sample(ids, ref_n)
  sel_id <- setdiff(ids, ref_id)

  phe_dt[!ID %in% ref_id, phe1 := NA_real_]
  phe_dt[!ID %in% ref_id, phe2 := NA_real_]

  fwrite(geno_dt, file.path(output_dir, "geno.csv"), sep = ",", quote = FALSE)
  fwrite(phe_dt, file.path(output_dir, "phe.csv"), sep = ",", quote = FALSE, na = "NA")
  fwrite(data.table(ID = ref_id), file.path(output_dir, "ref_id.csv"), sep = ",", quote = FALSE)
  fwrite(data.table(ID = sel_id), file.path(output_dir, "sel_id.csv"), sep = ",", quote = FALSE)

  invisible(list(
    geno = file.path(output_dir, "geno.csv"),
    phe = file.path(output_dir, "phe.csv"),
    ref_id = file.path(output_dir, "ref_id.csv"),
    sel_id = file.path(output_dir, "sel_id.csv")
  ))
}

main <- function() {
  args <- parse_args(commandArgs(trailingOnly = TRUE))

  fast_mode <- identical(Sys.getenv("HIBLUP_EBV_FAST_DEMO", unset = ""), "1")
  if (fast_mode) {
    args$n_ind <- min(args$n_ind, 24L)
    args$n_snp <- min(args$n_snp, 24L)
  }

  generate_demo(
    output_dir = args$output,
    n_ind = args$n_ind,
    n_snp = args$n_snp,
    seed = args$seed
  )
}

main()

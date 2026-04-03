suppressPackageStartupMessages(library(data.table))

makeped <- function(z) {
  z[!(z == 0 | z == 1 | z == 2)] <- -9
  z[z == 2] <- 22
  z[z == 1] <- 12
  z[z == 0] <- 11
  as.data.table(z, keep.rownames = "ID")
}

run_hiblup <- function(phename, trait_pos, addG = "", domG = "", out_prefix = "G_hib", threads = 32) {
  if (length(trait_pos) > 1) {
    trait_pos_str <- paste(trait_pos, collapse = " ")
    model_for_trait <- "--multi-trait"
  } else {
    trait_pos_str <- as.character(trait_pos)
    model_for_trait <- "--single-trait"
  }

  cmd <- paste(
    "hiblup",
    model_for_trait,
    "--pheno", phename,
    "--pheno-pos", trait_pos_str,
    "--xrm", paste(addG, domG, sep = ","),
    "--vc-method AI",
    "--ai-maxit 30",
    "--threads", threads,
    "--ignore-cove",
    "--out", out_prefix
  )
  system(cmd)

  results_dt <- fread(paste0(out_prefix, ".rand"), sep = "\t")
  dt_G <- results_dt[, .(ID, Prediction = get(addG))]

  if (domG != "") {
    dt_D <- results_dt[, .(ID, Prediction = get(domG))]
  } else {
    dt_D <- results_dt[, .(ID, Prediction = NA_real_)]
  }

  if (grepl("\\.GA$", addG)) {
    blup_models <- list(
      list(dt = dt_G, model = "gblup", comp = "add"),
      list(dt = dt_D, model = "gblup", comp = "dom")
    )
  } else if (grepl("\\.PA$", addG)) {
    blup_models <- list(
      list(dt = dt_G, model = "pblup", comp = "add"),
      list(dt = dt_D, model = "pblup", comp = "dom")
    )
  } else {
    blup_models <- list(list(dt = dt_G, model = "unknown", comp = "add"))
  }

  blup_models
}

estimate_ebv <- function(
  phe_file,
  geno_file,
  sel_id = NULL,
  ref_id = NULL,
  plink_format = FALSE,
  trait_pos = 4,
  threads = 32,
  workdir = "."
) {
  old <- getwd()
  on.exit(setwd(old), add = TRUE)
  setwd(workdir)

  if (!plink_format) {
    geno_dt <- fread(geno_file, sep = ",")
    ids <- geno_dt[[1]]
    geno_mat <- as.matrix(geno_dt[, -1])
    rownames(geno_mat) <- ids

    geno_ped <- makeped(geno_mat)
    fwrite(geno_ped, file = "hib.ped", col.names = FALSE, row.names = FALSE, quote = FALSE, sep = "\t")

    map_dt <- data.table(
      chr = rep(1, ncol(geno_mat)),
      id = colnames(geno_mat),
      pos = as.integer(seq_len(ncol(geno_mat))),
      gl = rep(0, ncol(geno_mat))
    )
    fwrite(map_dt, file = "hib.map", col.names = FALSE, row.names = FALSE, quote = FALSE, sep = " ")
  }

  mock_mode <- identical(Sys.getenv("HIBLUP_EBV_MOCK", unset = ""), "1")

  if (!mock_mode) {
    system("plink --file hib --geno --mind --no-sex --no-pheno --no-fid --no-parents --nonfounders --make-bed --chr-set 44 --out hib")
    system(sprintf("hiblup --make-xrm --threads %d --bfile hib --add --out Gmat_b", threads))

    gblup_models <- run_hiblup(
      phename = phe_file,
      trait_pos = trait_pos,
      addG = "Gmat_b.GA",
      domG = "",
      out_prefix = "G_hib",
      threads = threads
    )
    ebv <- copy(gblup_models[[1]]$dt)
  } else {
    phe_dt0 <- fread(phe_file, sep = ",")
    ebv <- data.table(
      ID = phe_dt0$ID,
      Prediction = seq_len(nrow(phe_dt0)) / max(1, nrow(phe_dt0))
    )
  }

  phe_dt <- fread(phe_file, sep = ",")
  phe_dt$ebv1 <- ebv$Prediction[match(phe_dt$ID, ebv$ID)]
  fwrite(phe_dt, file = "phe_ebv.csv", sep = ",", col.names = TRUE, row.names = FALSE, quote = FALSE, na = "NA")

  if (!is.null(sel_id) && nzchar(sel_id)) {
    sel_dt <- fread(sel_id, sep = ",")
    sel_dt$ebv1 <- ebv$Prediction[match(sel_dt$ID, ebv$ID)]
    fwrite(sel_dt, file = "sel_ebv.csv", sep = ",", col.names = TRUE, row.names = FALSE, quote = FALSE, na = "NA")
  }

  if (!is.null(ref_id) && nzchar(ref_id)) {
    ref_dt <- fread(ref_id, sep = ",")
    ref_dt$ebv1 <- ebv$Prediction[match(ref_dt$ID, ebv$ID)]
    fwrite(ref_dt, file = "ref_ebv.csv", sep = ",", col.names = TRUE, row.names = FALSE, quote = FALSE, na = "NA")
  }

  invisible("EBV estimation completed.")
}

parse_args <- function(args) {
  get_arg <- function(flag, default = NULL) {
    idx <- match(flag, args)
    if (is.na(idx) || idx == length(args)) return(default)
    args[[idx + 1]]
  }
  list(
    phe_file = get_arg("--phe-file", "phe.csv"),
    geno_file = get_arg("--geno-file", "geno.csv"),
    sel_id = get_arg("--sel-id", "sel_id.csv"),
    ref_id = get_arg("--ref-id", "ref_id.csv"),
    trait_pos = as.integer(get_arg("--trait-pos", "4")),
    threads = as.integer(get_arg("--threads", "32")),
    workdir = get_arg("--workdir", "."),
    plink_format = any(args == "--plink-format")
  )
}

main <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  opt <- parse_args(args)
  estimate_ebv(
    phe_file = opt$phe_file,
    geno_file = opt$geno_file,
    sel_id = opt$sel_id,
    ref_id = opt$ref_id,
    plink_format = opt$plink_format,
    trait_pos = opt$trait_pos,
    threads = opt$threads,
    workdir = opt$workdir
  )
}

main()

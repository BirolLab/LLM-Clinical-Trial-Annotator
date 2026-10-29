#!/usr/bin/env python3
"""Methodology 10.4 / 11.4 / 12.5 / 13.6 / 14.5 / 15.5 regression set.

usage: python3 -I delivery_mode_pipeline/regression.py <output.csv>
Every case was verified by hand in the run that added it; a failure means a
lexicon or guard change moved a row that is known to be right.
"""
import csv, sys, collections

INJ = "injection/infusion"
CASES = {
    # 10.4
    "NCT07582471": INJ, "NCT02472600": "Oral", "NCT01056965": "Other",
    "NCT02518022": INJ, "NCT02750501": "Oral", "NCT03680339": INJ,
    "NCT00571662": "Oral",
    # 11.4
    "NCT01135992": INJ, "NCT05439499": INJ, "NCT01240941": INJ,
    "NCT00102934": INJ, "NCT06624956": INJ, "NCT02189395": INJ,
    "NCT05107219": "Oral", "NCT02807363": "Oral", "NCT04064411": "Topical",
    "NCT02944110": "Unknown",
    # 12.5
    "NCT00659789": INJ, "NCT01712256": INJ, "NCT01965509": INJ,
    "NCT00639925": INJ, "NCT06429566": "Oral", "NCT01535027": INJ,
    "NCT01452685": INJ, "NCT03931915": INJ, "NCT07015268": INJ,
    "NCT05018637": INJ, "NCT00286429": INJ, "NCT07249554": "Oral",
    "NCT00468884": "Oral", "NCT00001386": INJ, "NCT00153569": INJ,
    "NCT00002916": INJ, "NCT05406635": "Unknown", "NCT02424708": "Other",
    "NCT02155803": INJ, "NCT03817125": "Oral",
    # 13.6
    "NCT02857582": "Oral", "NCT04918758": "Topical", "NCT05018286": INJ,
    "NCT02478710": "Other", "NCT01085760": "Oral", "NCT02397213": INJ,
    "NCT02186457": "Topical", "NCT02937896": "Other", "NCT02786992": INJ,
    "NCT01190163": INJ, "NCT00477763": "Topical", "NCT00502073": "Topical",
    "NCT04597762": "Topical", "NCT00167583": "Oral", "NCT01693393": "Oral",
    "NCT02285140": INJ, "NCT04401553": INJ, "NCT06527131": INJ,
    "NCT07004049": INJ, "NCT01266499": "Oral", "NCT02400112": "Topical",
    "NCT02631408": "Topical", "NCT05959603": "Topical", "NCT01372371": "Topical",
    "NCT00862875": INJ, "NCT02483299": INJ, "NCT01813227": INJ,
    "NCT02470039": INJ, "NCT06391853": "Other", "NCT00067015": INJ,
    # --- run 7 (methodology 14): the protein-biologic half of the corpus
    "NCT00407888": INJ,          # filgrastim "Given SC"
    "NCT00276029": INJ,          # etanercept, route only from the drug table
    "NCT00118638": INJ,          # darbepoetin alfa, route only from the drug table
    "NCT00001269": INJ,          # IL-3, abbreviation key
    "NCT03720340": INJ,          # rhIL-11, must cite interleukin 11 not interleukin 1
    "NCT00040521": "Oral",       # orally administered rhIL-11
    "NCT00005665": "Oral",       # "Ingested Interferon Alpha", must not be corrected
    "NCT00002719": INJ,          # rHuG-CSF trial, "oral schedule" is the chemo arm
    "NCT00514215": "Other",      # inhaled sargramostim
    "NCT00901511": "Other",      # inhaled GM-CSF
    "NCT00673179": INJ,          # sargramostim, chemo regimen in the same arm
    "NCT03943901": INJ,          # pegfilgrastim, R-CHOP arm text
    "NCT05170828": INJ,          # filgrastim, TBI ChEMBL flags must not answer
    "NCT06709495": INJ,          # pegfilgrastim, food/supplement class must not fire
    "NCT00506948": INJ,          # thymoglobulin, not oral MMF (CellCept is not -cept)
    "NCT01790594": INJ,          # belatacept + ATG, not oral MMF
    "NCT05996393": "Oral",       # ciclosporin orally; ATG IV must not win
    "NCT03180723": "Oral",       # oral cyclosporin; rituximab IV must not win
    "NCT05716009": INJ,          # tagraxofusp-erzs fusion protein
    "NCT01951729": INJ,          # GIP infusion (3-letter drug name)
    "NCT03516773": "Oral",       # EB612 oral PTH tablet
    "NCT00668850": "Other",      # Generex Oral-lyn buccal insulin spray
    "NCT00031551": "Topical",    # etanercept mouthwash
    "NCT02308436": "Topical",    # Curolox peptide mouthwash
    "NCT02999776": "Topical",    # topical etanercept via laser microporation
    "NCT00034788": "Topical",    # becaplermin (Regranex gel)
    "NCT05967325": "Other",      # self-assembling peptide nanofiber hydrogels (plural)
    "NCT06912815": INJ,          # ustekinumab + semi enteral nutrition
    "NCT04739371": "Other",      # intranasal insulin spray
    "NCT00000547": "Unknown",    # enalapril only - no peptide administered
    "NCT00170937": "Unknown",    # valsartan + HCTZ - no peptide administered
    "NCT01228279": "Unknown",    # Dianeal/Extraneal dialysate - no peptide drug
    # 15.5 -- run 8.  The identification gate (15.1) and the products verified
    # for it (15.3), plus the masks the gate's own fixes exposed (15.2).
    "NCT05660941": INJ,          # bare "Lispro" must resolve to insulin lispro
    "NCT03336528": INJ,          # bare Degludec/Glargine/Aspart
    "NCT00699686": INJ,          # bare Detemir/Glargine (Levemir/Lantus)
    "NCT00562133": INJ,          # insulin glulisine "before ingestion of a meal"
    "NCT00849576": INJ,          # regular human insulin, same meal wording
    "NCT03414333": INJ,          # GLP-1 "in response to nutrients ingestion"
    "NCT00982254": INJ,          # "subcutaneous injection of 15 U regular insulin"
    "NCT02004366": INJ,          # basal-bolus insulin, was Oral
    "NCT05220371": "Oral",       # "ingest 15 grams of collagen peptides"
    "NCT00005665": "Oral",       # "Ingested Interferon Alpha" (14.5, ORAL/ORALW)
    "NCT00356421": "Other",      # Exubera inhaled insulin is the study drug
    "NCT01445951": "Other",      # Technosphere insulin inhaler
    "NCT05243628": "Other",      # Afrezza inhalation powder
    "NCT03352349": INJ,          # "Terlipressinum" - Latin INN ending
    "NCT04242017": INJ,          # "Triptoreline" - French INN ending
    "NCT05933720": INJ,          # "Polypeptides" must rank as a peptide
    "NCT03589443": "Topical",    # "Multiplexed heptapeptides"
    "NCT05121831": "Oral",       # DGX-001 - route table names the product
    "NCT01925261": INJ,          # TPX-100 intra-articular (verified 15.3)
    "NCT01590758": "Topical",    # MSI-78/pexiganan cream
    "NCT05778188": INJ,          # RLS-0071 - peptide status verified, record route
    "NCT01854294": INJ,          # GM604 six-amino-acid MNTF analogue
    "NCT03651089": INJ,          # SP16 subcutaneous
    "NCT04701021": INJ,          # TENDU peptide vaccine
    "NCT05603598": INJ,          # LEAP-2 IV infusion
    "NCT01236404": INJ,          # PB1023 weekly SC
    "NCT01416038": INJ,          # DPX-Survivac survivin peptide vaccine
    "NCT00107211": INJ,          # peptide-pulsed DC vaccine (record-level class)
    "NCT00243529": INJ,          # peptide-pulsed vs RNA-transfected DC vaccine
    "NCT00445419": INJ,          # virosome-formulated peptides vaccine
    "NCT00079495": INJ,          # altered peptide ligand NBI-5788
    "NCT00467506": INJ,          # di-DTPA-131I peptide (radioiodine in ISOTOPE)
    "NCT05553184": "Unknown",    # formoterol + 18F substudy is not a peptide trial
    "NCT00853944": "Unknown",    # sitagliptin only - no peptide administered
    "NCT07435090": "Unknown",    # rimegepant ODT only
    "NCT02148978": "Unknown",    # saxagliptin only
    "NCT04283318": "Unknown",    # "12h/36h fasting" - no agent at all
    "NCT06669273": "Unknown",    # "CEST MRI sequence at 3T"
    "NCT06333717": "Unknown",    # whole grain vs control bread
    "NCT05319301": "Unknown",    # melatonin only
    "NCT06105060": "Unknown",    # rosuvastatin only
    "NCT02020395": "Unknown",    # "test meal (500 kcal)" - was Topical
    "NCT02370927": "Unknown",    # pea protein/starch/fibre
    "NCT07404358": INJ,          # "Dalargin is a ... opioid peptide" (self-definition)
    "NCT07581613": "Topical",    # "hydrogel incorporating proline-rich peptides"
    "NCT05220371": "Oral",       # "ingest 15 grams of collagen peptides"
    "NCT00853944": "Unknown",    # sitagliptin desc mentions insulin - not self-definition
    # 16.5 -- run 9.  Route words owned by a cell-product or imaging-agent
    # procedure, the peptide's own intervention description, and the products
    # verified for the Unknown bucket's named-peptide blanks.
    "NCT01144000": INJ, "NCT02867800": "Oral", "NCT00741455": "Oral",
    "NCT00001880": "Oral", "NCT00005941": "Oral", "NCT00006233": "Oral",
    "NCT00209859": "Oral", "NCT00806598": "Oral", "NCT01002339": "Oral",
    "NCT01259544": "Oral", "NCT03381768": INJ, "NCT04051307": INJ,
    "NCT07516756": "Oral", "NCT00504608": INJ, "NCT00664573": INJ,
    "NCT00664716": INJ, "NCT01288339": INJ, "NCT06430671": INJ,
    "NCT00669786": INJ, "NCT04176328": "Other", "NCT05251610": INJ,
    "NCT02130414": "Oral", "NCT00460382": INJ, "NCT06713187": "Unknown",
    "NCT01909141": "Unknown", "NCT00134394": INJ, "NCT07262957": INJ,
    "NCT02834468": "Oral", "NCT07039747": "Oral", "NCT05119322": "Unknown",
    "NCT05427448": "Unknown", "NCT07061301": "Unknown", "NCT02571140": "Oral",
}

rows = {r["NCT Number"]: r for r in csv.DictReader(open(sys.argv[1], newline=""))}
bad = 0
absent = sorted(n for n in CASES if n not in rows)
if absent:
    print(f"{len(absent)} case ids are not in this trial set (out of scope, skipped):",
          " ".join(absent))
for nct, want in sorted(CASES.items()):
    if nct not in rows:
        continue
    got = rows[nct]["Delivery Mode"]
    if got != want:
        bad += 1
        print(f"FAIL {nct}: expected {want}, got {got}")
        print(f"     {rows.get(nct, {}).get('Evidence', '')[:200]}")
n_in = len(CASES) - len(absent)
print(f"{n_in - bad}/{n_in} in-scope regression cases pass")
print(collections.Counter(r["Delivery Mode"] for r in rows.values()).most_common())
print(collections.Counter(r["Confidence"] for r in rows.values()).most_common())
sys.exit(1 if bad else 0)

"""Apply manually curated 18m vacancy employer websites (no HTTP / crawling).

Parent consolidation: only the parent org gets a website in seed+master.
Branch / site vacancy rows stay without websites so they do not match separately.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glos_recommender.labels import public_employer_website  # noqa: E402

SEED = ROOT / "data" / "seed" / "companies_seed.csv"
MASTER = ROOT / "app" / "app_data" / "companies_master.csv"


def norm_url(raw: str) -> str:
    u = str(raw or "").strip()
    if not u or u.lower().startswith("no "):
        return ""
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    return public_employer_website(u) or u


def max_glc_id(seed: pd.DataFrame) -> int:
    max_id = 0
    for cid in seed["company_id"].astype(str):
        if cid.startswith("GLC") and cid[3:].isdigit():
            max_id = max(max_id, int(cid[3:]))
    return max_id


def name_mask(df: pd.DataFrame, pattern: str) -> pd.Series:
    return df["name"].astype(str).str.contains(pattern, case=False, na=False, regex=True)


# Parent company_id(s) to set website on, plus name patterns whose websites must stay blank.
# website values are user-supplied careers/main sites (manual curation only).
PARENTS: list[dict] = [
    # --- Batch 1 ---
    {
        "ids": ["VAC2EDC147E"],
        "website": "https://join.specsavers.com/uk",
        "seed_name": "Specsavers Optical Superstores Limited",
        "clear": r"^SPECSAVERS\b",
        "clear_except_ids": ["VAC2EDC147E"],
    },
    {
        "ids": ["VAC6E81C21A"],
        "website": "https://careers.aviva.com",
        "seed_name": "Aviva PLC",
    },
    {
        "ids": ["VACCD16C9E2"],
        "website": "https://www.babcockinternational.com/careers",
        "seed_name": "Babcock International",
    },
    {
        "ids": ["VACA80294CD"],
        "website": "https://www.barchesterjobs.com",
        "seed_name": "Barchester Healthcare Limited",
        "clear": r"Barchester Healthcare",
        "clear_except_ids": ["VACA80294CD"],
    },
    {
        "ids": ["VAC3EB4147C"],
        "website": "https://www.bristolairport.co.uk/about-us/careers",
        "seed_name": "Bristol Airport Limited",
    },
    {
        "ids": ["VAC62A13D33"],
        "website": "https://www.daylewis.co.uk/careers",
        "seed_name": "Day Lewis PLC",
    },
    {
        "ids": ["VAC4ABAB54C"],
        "website": "https://careers.dhl.com",
        "seed_name": "DHL Global Forwarding (UK) Limited",
        "clear": r"^DHL\b",
        "clear_except_ids": ["VAC4ABAB54C"],
    },
    {
        "ids": ["VACB8870689"],
        "website": "https://careers.gknaerospace.com",
        "seed_name": "GKN Aerospace Services Limited",
    },
    {
        "ids": ["VAC0A7CEE42"],
        "website": "https://careers.ianwilliams.co.uk",
        "seed_name": "Ian Williams Limited",
    },
    {
        "ids": ["VAC3C97F543"],
        "website": "https://jobs.johnsoncontrols.com",
        "seed_name": "Johnson Controls Building Efficiency UK Limited",
    },
    {
        "ids": ["VACDE21C160"],
        "website": "https://www.nccgroup.com/uk/careers",
        "seed_name": "NCC Operations Limited",
    },
    {
        "ids": ["VACA379700B"],
        "website": "https://www.phinia.com/careers",
        "seed_name": "Phinia Delphi UK Ltd",
    },
    {
        "ids": ["GLC001", "GLC121"],
        "website": "https://www.renishaw.com/en/careers",
        "seed_name": "Renishaw",
    },
    {
        "ids": ["VAC6AE661F4"],
        "website": "https://jobs.royalmailgroup.com",
        "seed_name": "Royal Mail Group Limited",
    },
    {
        "ids": ["VACB02D77BE"],
        "website": "https://www.seetru.com/careers",
        "seed_name": "Seetru Limited",
    },
    {
        "ids": ["GLC204", "VACCD95ED8C"],
        "website": "https://stantec.jobs",
        "seed_name": "Stantec UK Limited",
        "clear": r"Stantec|HYDROCK CONSULTANTS|Hydrock",
        "clear_except_ids": ["GLC204", "VACCD95ED8C"],
    },
    {
        "ids": ["VACD07AB080"],
        "website": "https://www.whistl.co.uk/careers",
        "seed_name": "Whistl Limited",
    },
    {
        "ids": ["GLC013"],
        "website": "https://www.gloucestershire.gov.uk/jobs-and-careers",
        "seed_name": "Gloucestershire County Council",
    },
    {
        "ids": ["VAC29013093"],
        "website": "https://www.nbt.nhs.uk/careers",
        "seed_name": "North Bristol NHS Trust",
    },
    {
        "ids": ["VAC90E8A760"],
        "website": "https://www.oclcareers.org",
        "seed_name": "Oasis Community Learning",
        "clear": r"Oasis",
        "clear_except_ids": ["VAC90E8A760"],
    },
    {
        "ids": ["VACCE20C87F"],
        "website": "https://jobs.southglos.gov.uk",
        "seed_name": "South Gloucestershire Council",
    },
    {
        "ids": ["VAC46F29625"],
        "website": "https://www.stmonicatrust.org.uk/jobs",
        "seed_name": "St Monica Trust",
    },
    {
        "ids": ["VAC2E2D314B"],
        "website": "https://www.stroud.gov.uk/job-vacancies",
        "seed_name": "Stroud District Council",
    },
    {
        "ids": ["VACFEDEA92D"],
        "website": "https://www.bristol.ac.uk/jobs",
        "seed_name": "University of Bristol",
    },
    {
        "ids": ["VAC61AC12FC"],
        "website": "https://www.youngglos.org.uk/about-us/work-for-us",
        "seed_name": "Young Gloucestershire",
    },
    {
        "ids": ["VAC3E038AF8"],
        "website": "https://www.inspireata.co.uk",
        "seed_name": "Inspire ATA Limited",
    },
    {
        "ids": ["VAC8C1D6022"],
        "website": "https://www.justchildcare.co.uk/careers",
        "seed_name": "Just Childcare Limited",
    },
    {
        "ids": ["VAC2A613F55"],
        "website": "https://www.mamabear.co.uk/careers",
        "seed_name": "Mama Bear's Day Nursery Ltd",
        "clear": r"Mama Bear",
        "clear_except_ids": ["VAC2A613F55"],
    },
    {
        "ids": ["VAC14247E6E"],
        "website": "https://www.professionalapprenticeships.co.uk",
        "seed_name": "Professional Apprenticeships Ltd",
    },
    {
        "ids": ["VACA453ED9E"],
        "website": "https://www.myshine.co.uk/jobs",
        "seed_name": "Shine Wraparound Care Ltd",
    },
    {
        "ids": ["VAC45EAC19B"],
        "website": "https://www.snapdragonsnurseries.com/careers",
        "seed_name": "Snapdragons Nurseries Limited",
    },
    {
        "ids": ["VAC3701D56B"],
        "website": "https://www.theswac.org.uk/current-vacancies",
        "seed_name": "South West Apprenticeship Company Ltd",
    },
    {
        "ids": ["VAC2A0567A8"],
        "website": "https://careers.brighthorizons.com",
        "seed_name": "The Childcare Corporation Limited",
    },
    {
        "ids": ["GLC023", "VAC1B9F597D"],
        "website": "https://jobs.greeneking.co.uk",
        "seed_name": "Greene King Retail Services Limited",
        "clear": r"Greene King|Henbury - Bristol|Brimsham Park|Little Harp|Old Manse Hotel|Royal Oak \(Bishops Cleeve\)",
        "clear_except_ids": ["GLC023", "VAC1B9F597D"],
    },
    {
        "ids": ["VAC9FD06A87"],
        "website": "https://www.mbcareersandjobs.com",
        "seed_name": "Mitchells & Butlers Leisure Retail Limited",
        "clear": r"Mitchells|& Butlers|Miller and Carter|Harvester -|Brassmills",
        "clear_except_ids": ["VAC9FD06A87"],
    },
    {
        "ids": [],  # new seed parent; branches cleared
        "website": "https://www.thecoconut-tree.com/careers",
        "seed_name": "The Coconut Tree",
        "town": "Bristol",
        "clear": r"Coconut Tree|MPS HOSPITALITY",
        "clear_except_ids": [],
    },
    {
        "ids": ["VACB1179FFC"],
        "website": "https://www.mydentistcareers.co.uk",
        "seed_name": "IDH Group Limited (My Dentist)",
        "clear": r"IDH GROUP|My Dentist",
        "clear_except_ids": ["VACB1179FFC"],
    },
    {
        "ids": ["VAC4630C8A8"],
        "website": "https://www.rodericksdentalcareers.co.uk",
        "seed_name": "Rodericks Dental Holdings Limited",
        "clear": r"Rodericks",
        "clear_except_ids": ["VAC4630C8A8"],
    },
    # AtkinsRéalis (vacancy name may have encoding issues)
    {
        "ids": ["VACC968FE65"],
        "website": "https://careers.atkinsrealis.com",
        "seed_name": "AtkinsRéalis",
        "clear": r"^ATKINS LIMITED$",
        "clear_except_ids": ["VACC968FE65"],
    },
    # --- Batch 2 ---
    {
        "ids": ["VAC08E7BB95"],
        "website": "https://www.greenlightsc.co.uk",
        "seed_name": "Greenlight Safety & Consultancy Ltd",
        "clear": r"GREENLIGHT SAFETY|GREENLIGHT TRAINING|Greenlight Safety|Greenlight Training",
        "clear_except_ids": ["VAC08E7BB95", "GLC224"],
    },
    {
        "ids": ["VAC7A484926"],
        "website": "https://oceanhome.co.uk/conveyancing",
        "seed_name": "Ocean Property Lawyers Ltd",
    },
    {
        "ids": ["VAC7A8C3AF1"],
        "website": "https://design4life.uk",
        "seed_name": "Design 4 Life Limited",
    },
    {
        "ids": ["VACABD4B009"],
        "website": "https://www.theatateam.co.uk/eda",
        "seed_name": "EDA Learning and Development Limited",
    },
    {
        "ids": ["VACFCD2CFBC"],
        "website": "https://edisonfordinsure.co.uk",
        "seed_name": "Edison Ford Gen Insurance Brokers",
    },
    {
        "ids": ["VAC90DCAAF0"],
        "website": "https://dalcourmaclaren.com/careers",
        "seed_name": "Dalcour Maclaren Limited",
    },
    {
        "ids": ["VAC98D89D0B"],
        "website": "https://jobs.persimmonhomes.com",
        "seed_name": "Persimmon Homes Limited",
    },
    {
        "ids": ["VACF5A2D9C3"],
        "website": "https://weare5values.com",
        "seed_name": "5Values Consulting Group Ltd",
        "clear": r"5Values|5VALUES",
        "clear_except_ids": ["VACF5A2D9C3"],
    },
    {
        "ids": ["VACC69D50D2"],
        "website": "https://lancerscott.co.uk/careers",
        "seed_name": "Lancer Scott Limited",
    },
    {
        "ids": ["VACD28C8196"],
        "website": "https://careers.muller.co.uk",
        "seed_name": "Muller UK & Ireland Group LLP",
    },
    {
        "ids": ["VAC70F6A038"],
        "website": "https://nasaconsulting.com",
        "seed_name": "Nasa Consulting Limited",
    },
    {
        "ids": ["VAC3DB7D3F9"],
        "website": "https://careers.publicagroup.uk",
        "seed_name": "Publica Group (Support) Limited",
    },
    {
        "ids": ["VAC542B8E65"],
        "website": "https://rhclifting.com",
        "seed_name": "R H C Lifting Ltd",
    },
    {
        "ids": ["VAC4ED924D4"],
        "website": "https://www.eteach.com/careers/raisedinbristol",
        "seed_name": "Raised in Bristol Ltd",
    },
    {
        "ids": ["VACB720791A"],
        "website": "https://www.rheinmetall.com/en/career",
        "seed_name": "Rheinmetall MAN Military Vehicles UK Ltd",
        "clear": r"RHEINMETALL",
        "clear_except_ids": ["VACB720791A"],
    },
    {
        "ids": ["VAC3459B32A"],
        "website": "https://www.smartsystems.co.uk/careers",
        "seed_name": "Smart Systems Limited",
    },
    {
        "ids": ["VAC464D0A4C"],
        "website": "https://www.tarmac.com/careers",
        "seed_name": "Tarmac Trading Limited",
        "clear": r"^Tarmac\b|^TARMAC\b",
        "clear_except_ids": ["VAC464D0A4C"],
    },
    {
        "ids": ["VACC0F655CD"],
        "website": "https://acservicessouthern.co.uk",
        "seed_name": "AC Services (Southern) Limited",
    },
    {
        "ids": ["VAC5E41B994"],
        "website": "https://www.bristol.gov.uk/jobs-and-careers",
        "seed_name": "Bristol City Council",
        "clear": r"Bristol City Council",
        "clear_except_ids": ["VAC5E41B994"],
    },
    {
        "ids": ["VAC8C35CC36"],
        "website": "https://prisonandprobationjobs.gov.uk",
        "seed_name": "HM Prison & Probation Service",
    },
    {
        "ids": ["VACF2E2861F"],
        "website": "https://careers.mod.uk",
        "seed_name": "Ministry of Defence",
    },
    {
        "ids": ["VAC44B2C34B"],
        "website": "https://careers.bupa.co.uk",
        "seed_name": "Bupa (British United Provident Association)",
        "clear": r"\bBupa\b|\bBUPA\b|British United Provident",
        "clear_except_ids": ["VAC44B2C34B"],
    },
    {
        "ids": ["VACCD7CB335"],
        "website": "https://n-somerset.gov.uk/my-services/jobs-training/council-jobs",
        "seed_name": "North Somerset Council",
    },
    {
        "ids": ["VAC83BD32AE"],
        "website": "https://www.blc.school",
        "seed_name": "Bridge Learning Campus",
    },
    {
        "ids": ["VAC4DB3DFDE"],
        "website": "https://christchurchinfants.co.uk",
        "seed_name": "Christ Church Infant School",
    },
    {
        "ids": ["VACFB2A89CF"],
        "website": "https://gloucesterroadprimary.co.uk",
        "seed_name": "Gloucester Road Primary School",
        "clear": r"Gloucester Road Primary",
        "clear_except_ids": ["VACFB2A89CF"],
    },
    {
        "ids": ["VAC42CE22C9"],
        "website": "https://ravenswoodschool.org.uk",
        "seed_name": "Ravenswood School",
    },
    {
        "ids": ["VACF4566E22"],
        "website": "https://barbarnursery.co.uk",
        "seed_name": "Barbar Nursery Limited",
    },
    {
        "ids": ["VAC76E7BB1E"],
        "website": "https://avonvalleynursery.co.uk",
        "seed_name": "Avon Valley Nursery and Pre School",
    },
    {
        "ids": ["VACE06848B0"],
        "website": "https://daisychain-nursery.co.uk",
        "seed_name": "Daisychain Bristol Ltd",
    },
    {
        "ids": ["VACC5A1594E"],
        "website": "https://grandiruk.com/careers",
        "seed_name": "Grandir UK",
    },
    {
        "ids": ["VACE8769CF3"],
        "website": "https://minivips.co.uk",
        "seed_name": "Mini VIP's Nursery & Day Care Ltd",
    },
    {
        "ids": ["VACC20396F9"],
        "website": "https://quaysparknursery.co.uk",
        "seed_name": "Quays Park Nursery",
    },
    {
        "ids": ["VAC9A2D56BC"],
        "website": "https://www.theoldstationnursery.co.uk/careers",
        "seed_name": "The Old Station Nursery",
    },
    {
        "ids": ["VACDB7752DD"],
        "website": "https://marstonscareers.co.uk",
        "seed_name": "Marston's PLC",
        "clear": r"Marston",
        "clear_except_ids": ["VACDB7752DD"],
    },
    # --- Batch 3 ---
    {
        "ids": ["VAC719A5CA2"],
        "website": "https://careers.griffiths.co.uk",
        "seed_name": "Alun Griffiths (Contractors) Limited",
    },
    {
        "ids": ["VAC69206263"],
        "website": "https://jobs.bt.com",
        "seed_name": "BT Group PLC",
    },
    {
        "ids": ["VACA7BBDB93"],
        "website": "https://cfroberts.co.uk",
        "seed_name": "CF Roberts (Electrical Contractors) Limited",
    },
    {
        "ids": ["VAC6DF9C708"],
        "website": "https://chartwellfunding.co.uk",
        "seed_name": "Chartwell Funding Limited",
    },
    {
        "ids": ["GLC179"],
        "website": "https://careers.cruxproductdesign.com",
        "seed_name": "Crux Product Design Ltd",
    },
    {
        "ids": ["VACB6A18F6C"],
        "website": "https://flex-digital.net",
        "seed_name": "Flex Digital Solutions Ltd",
    },
    {
        "ids": ["VAC44DAB618"],
        "website": "https://fmgrepairservices.co.uk/careers",
        "seed_name": "FMG Repair Services Limited",
    },
    {
        "ids": ["VACDF9BCBD6"],
        "website": "https://gap-group.co.uk/work-with-us",
        "seed_name": "GAP Group Limited",
    },
    {
        "ids": ["VACAAE7A19A"],
        "website": "https://careers.jacobs.com",
        "seed_name": "Jacobs U.K. Limited",
    },
    {
        "ids": ["VACDEAEC8D8"],
        "website": "https://konecranes.careers",
        "seed_name": "Konecranes UK Limited",
    },
    {
        "ids": ["VAC6EF27BE8"],
        "website": "https://careers.man.co.uk",
        "seed_name": "MAN Truck and Bus UK Limited",
    },
    {
        "ids": ["VACB4082546"],
        "website": "https://nrs.careers",
        "seed_name": "Nuclear Restoration Services",
    },
    {
        "ids": ["VAC792A58BF"],
        "website": "https://pegasusgroup.co.uk/careers",
        "seed_name": "Pegasus Planning Group Limited",
    },
    {
        "ids": ["VACD5A2D998"],
        "website": "https://www.rpclegal.com/careers",
        "seed_name": "Reynolds Porter Chamberlain LLP (RPC)",
    },
    {
        "ids": ["VAC316948AC"],
        "website": "https://rightonblackburns.co.uk",
        "seed_name": "Righton Blackburns",
    },
    {
        "ids": ["VAC569734F2"],
        "website": "https://www.scania.com/uk/en/home/careers",
        "seed_name": "Scania (Great Britain) Limited",
    },
    {
        "ids": ["VACC22D93C9"],
        "website": "https://www.sjp.co.uk/careers",
        "seed_name": "St. James's Place Management Services Limited",
    },
    {
        "ids": ["VAC771CA7CF"],
        "website": "https://stathamcustomcabinsltd.co.uk",
        "seed_name": "Statham Custom Cabins Ltd",
    },
    {
        "ids": ["VACF36A4BFF"],
        "website": "https://thewaitinggame.co.uk",
        "seed_name": "The Waiting Game (Bristol) Limited",
    },
    {
        "ids": ["VACBB07434E"],
        "website": "https://careers.tuigroup.com/en/united-kingdom",
        "seed_name": "TUI UK Limited",
    },
    {
        "ids": ["VAC92039095"],
        "website": "https://careers.thatcherscider.co.uk",
        "seed_name": "Thatchers Cider Company Ltd",
    },
    {
        "ids": ["VACD9824201"],
        "website": "https://timberwindows.com",
        "seed_name": "Timber Windows Cotswolds",
    },
    {
        "ids": ["VAC9E8FE20A"],
        "website": "https://www.arjo.com/en-gb/about-us/careers",
        "seed_name": "Arjo UK Limited",
    },
    {
        "ids": ["VAC95AB33CC"],
        "website": "https://ascentflighttraining.com/careers",
        "seed_name": "Ascent Flight Training (Management) Limited",
    },
    {
        "ids": ["VAC258D0327"],
        "website": "https://bristol-sport.co.uk/careers/work-at-ashton-gate",
        "seed_name": "Ashton Gate Limited",
    },
    {
        "ids": ["VAC19008691"],
        "website": "https://www.atseuromaster.co.uk",
        "seed_name": "ATS Euromaster Limited",
    },
    {
        "ids": ["VAC65F84C80"],
        "website": "https://jobs.arup.com",
        "seed_name": "Arup",
        "clear": r"\bArup\b|OVE ARUP",
        "clear_except_ids": ["VAC65F84C80"],
    },
    {
        "ids": ["VACC3C0374F"],
        "website": "https://careers.bca.co.uk",
        "seed_name": "British Car Auctions Limited (BCA)",
        "clear": r"British Car Auctions|BRITISH CAR AUCTIONS|\bBCA\b",
        "clear_except_ids": ["VACC3C0374F"],
    },
    {
        "ids": ["VAC234B60FD"],
        "website": "https://coachcore.org.uk/about-us/careers",
        "seed_name": "Coach Core Foundation",
    },
    {
        "ids": ["GLC289", "VACBC496A0B"],
        "website": "https://www.civil-service-careers.gov.uk/dvsa",
        "seed_name": "DVSA",
        "clear": r"Driver and Vehicle Standards Agency|^DVSA$",
        "clear_except_ids": ["GLC289", "VACBC496A0B"],
    },
    {
        "ids": ["VAC8333C1D6"],
        "website": "https://defrajobs.co.uk",
        "seed_name": "Defra",
    },
    {
        "ids": ["VACDC40AC89"],
        "website": "https://www.gloscol.ac.uk/jobs-at-gc",
        "seed_name": "Gloucestershire College",
    },
    {
        "ids": ["VAC16C63624"],
        "website": "https://horseworld.org.uk/about-us/vacancies",
        "seed_name": "HorseWorld Trust",
    },
    {
        "ids": ["VAC02756F67"],
        "website": "https://stchadsprimaryschool.co.uk",
        "seed_name": "St Chad's CE VC Primary School",
    },
    {
        "ids": ["VACE5F9A8BC"],
        "website": "https://www.tewkesbury.gov.uk/jobs",
        "seed_name": "Tewkesbury Borough Council",
    },
    {
        "ids": ["VAC65805C91"],
        "website": "https://abbotswood.s-gloucs.sch.uk",
        "seed_name": "Abbotswood Primary School",
    },
    {
        "ids": ["VACC87E95C6"],
        "website": "https://swinefordnursery.co.uk",
        "seed_name": "Swineford Nursery & Pre School Ltd",
    },
    {
        "ids": ["VAC2B3D034A"],
        "website": "https://twinkletotsdaynursery.co.uk",
        "seed_name": "Twinkle Tots Childcare",
    },
    {
        "ids": ["VAC868C6831"],
        "website": "https://cirencesterdentalandaesthetics.com",
        "seed_name": "Cirencester Dental & Aesthetics",
        "clear": r"Cirencester Dental",
        "clear_except_ids": ["VAC868C6831"],
    },
    {
        "ids": ["VAC9FACF5CE"],
        "website": "https://jhootspharmacy.co.uk/careers",
        "seed_name": "Jhoots Healthcare",
        "clear": r"Jhoots|JHOOTS",
        "clear_except_ids": ["VAC9FACF5CE"],
    },
    {
        "ids": ["VAC628FF21F"],
        "website": "https://uicare.co.uk",
        "seed_name": "Ultimate Independence Care Ltd",
        "clear": r"Ultimate Independence Care",
        "clear_except_ids": ["VAC628FF21F"],
    },
    {
        "ids": ["VAC0EA0D4B1"],
        "website": "https://fattonis.co.uk",
        "seed_name": "Fat Tonis Franchise Management Ltd",
    },
    # --- Batch 4 ---
    {
        "ids": ["VAC0008C5B0"],
        "website": "https://bradmanlake.com/careers",
        "seed_name": "Bradman Lake",
    },
    {
        "ids": ["VAC2D07CD3F"],
        "website": "https://jobs.dsv.com",
        "seed_name": "DSV Road",
        "clear": r"\bDSV\b",
        "clear_except_ids": ["VAC2D07CD3F"],
    },
    {
        "ids": ["VACA94CE1CD"],
        "website": "https://emcoruk.com/careers",
        "seed_name": "EMCOR (UK) LIMITED",
    },
    {
        "ids": ["VACFF6647E7"],
        "website": "https://envolve-infrastructure.co.uk/company/careers",
        "seed_name": "ENVOLVE",
    },
    {
        "ids": ["VAC27BF9A0E"],
        "website": "https://farmfoods.co.uk/careers.php",
        "seed_name": "FARMFOODS",
    },
    {
        "ids": ["VAC62D7089B"],
        "website": "https://heidelbergmaterials.co.uk/en/careers",
        "seed_name": "Heidelberg Materials",
        "clear": r"Hanson|Heidelberg",
        "clear_except_ids": ["VAC62D7089B"],
    },
    {
        "ids": ["VAC27B1C471"],
        "website": "https://harbour-facades.co.uk",
        "seed_name": "Harbour Facade Systems Ltd",
    },
    {
        "ids": ["VAC52D88F74"],
        "website": "https://ibstock.co.uk/careers",
        "seed_name": "IBSTOCK BRICK LIMITED",
        "clear": r"Ibstock|IBSTOCK",
        "clear_except_ids": ["VAC52D88F74"],
    },
    {
        "ids": ["VAC9A87CBEF"],
        "website": "https://jacksonlifts.com/careers",
        "seed_name": "JACKSON LIFT",
    },
    {
        "ids": ["VAC547A5638"],
        "website": "https://lb-bentley.com",
        "seed_name": "L.B. BENTLEY",
    },
    {
        "ids": ["VAC689A6F38"],
        "website": "https://lloydsbankinggroup.com/careers.html",
        "seed_name": "Lloyds Banking Group",
    },
    {
        "ids": ["VACCB3ED4B3"],
        "website": "https://monmotors.com/careers",
        "seed_name": "MON MOTORS",
        "clear": r"Mon Motors|MON MOTORS",
        "clear_except_ids": ["VACCB3ED4B3"],
    },
    {
        "ids": ["VAC539B2F4F"],
        "website": "https://careers.nationalgrid.com",
        "seed_name": "National Grid",
        "clear": r"National Grid",
        "clear_except_ids": ["VAC539B2F4F"],
    },
    {
        "ids": ["VACB11EDD34"],
        "website": "https://oliverconnell.com/Careers.html",
        "seed_name": "Oliver Connell",
    },
    {
        "ids": ["VACDBF1C35F"],
        "website": "https://origin8tive.com/careers",
        "seed_name": "ORIGIN8TIVE",
    },
    {
        "ids": ["VAC7EFDBD0F"],
        "website": "https://paragonskills.co.uk/vacancies",
        "seed_name": "Paragon Skills",
        "clear": r"Paragon",
        "clear_except_ids": ["VAC7EFDBD0F"],
    },
    {
        "ids": ["VACE287CD7F"],
        "website": "https://phc.parts",
        "seed_name": "PHC Parts - Bristol",
        "clear": r"^PHC Parts",
        "clear_except_ids": ["VACE287CD7F"],
    },
    {
        "ids": ["VACDBBB833F"],
        "website": "https://uk.ramboll.com/careers",
        "seed_name": "Ramboll",
    },
    {
        "ids": ["VACADA3D4C7"],
        "website": "https://socomec.co.uk/en-gb/socomec/careers",
        "seed_name": "SOCOMEC",
    },
    {
        "ids": ["VAC2AD53754"],
        "website": "https://solumsw.co.uk",
        "seed_name": "SOLUM",
    },
    {
        "ids": ["VACFF181C57"],
        "website": "https://spectrumit.co.uk",
        "seed_name": "SPECTRUM IT CONSULTANCY",
    },
    {
        "ids": ["VAC703C9E77"],
        "website": "https://treeshopplants.co.uk",
        "seed_name": "TREE SHOP LTD",
    },
    {
        "ids": ["VAC47AA36A3"],
        "website": "https://trustsystems.co.uk/careers",
        "seed_name": "TRUST SYSTEMS",
    },
    {
        "ids": ["VAC92BE8807"],
        "website": "https://uksgroup.co.uk",
        "seed_name": "UKS Group",
        "clear": r"UKS Group|UKS GROUP",
        "clear_except_ids": ["VAC92BE8807"],
    },
    {
        "ids": ["GLC164"],
        "website": "https://clf.uk/careers",
        "seed_name": "Cabot Learning Federation",
        "clear": r"Frome Vale Academy",
        "clear_except_ids": ["GLC164"],
    },
    {
        "ids": ["VAC136DD30E"],
        "website": "https://www.civil-service-careers.gov.uk/departments/hm-revenue-and-customs",
        "seed_name": "HM Revenue & Customs",
    },
    {
        "ids": ["VAC8B1D3EF4"],
        "website": "https://ourladyandstswithins.org.uk",
        "seed_name": "Our Lady and St Swithin's Catholic Primary School",
    },
    {
        "ids": ["VACD648B47B"],
        "website": "https://pucklechurchprimary.org.uk",
        "seed_name": "Pucklechurch CE VC Primary",
        "clear": r"Pucklechurch",
        "clear_except_ids": ["VACD648B47B"],
    },
    {
        "ids": ["VACA9E26B5D"],
        "website": "https://sgscol.ac.uk/jobs",
        "seed_name": "South Gloucestershire and Stroud College",
    },
    {
        "ids": ["VAC03BA007D"],
        "website": "https://officeforstudents.org.uk/about/working-for-us",
        "seed_name": "Office for Students",
    },
    {
        "ids": ["VAC454C3449"],
        "website": "https://rehabilityuk.co.uk",
        "seed_name": "Rehability UK",
    },
    {
        "ids": ["VAC0C8D8684"],
        "website": "https://glo-childcare.co.uk",
        "seed_name": "GLO CHILDCARE",
    },
    {
        "ids": ["VAC6A9C2CA1"],
        "website": "https://littleacornswsm.co.uk",
        "seed_name": "LITTLE ACORNS (WSM) LTD",
        "clear": r"LITTLE ACORNS",
        "clear_except_ids": ["VAC6A9C2CA1"],
    },
    {
        "ids": ["VAC35BBE340"],
        "website": "https://partou.co.uk/careers",
        "seed_name": "Partou - Westfields Day Nursery and Pre-school",
        "clear": r"Partou",
        "clear_except_ids": ["VAC35BBE340"],
    },
    {
        "ids": ["VACE1CC7C29"],
        "website": "https://tigermartialarts.club",
        "seed_name": "Tiger Martial Arts",
    },
    {
        "ids": ["VAC6C6C4E1E"],
        "website": "https://dreammakertravel.co.uk",
        "seed_name": "DREAM MAKER TRAVEL LTD",
    },
    {
        "ids": ["VAC7A88808A"],
        "website": "https://tomrowlandeventing.com",
        "seed_name": "Tom Rowland Eventing",
    },
    # --- Batch 5 ---
    {
        "ids": ["VACE4CA040E"],
        "website": "https://inflectionpoint.uk",
        "seed_name": "Inflection Point MSP Ltd",
    },
    {
        "ids": ["VAC0F197925"],
        "website": "https://www.iress.com/join-us/careers",
        "seed_name": "Iress FS Limited",
    },
    {
        "ids": ["VAC9BBC5B4D"],
        "website": "https://kestrelvalve.co.uk",
        "seed_name": "Kestrel Valve & Engineering Services Ltd",
    },
    {
        "ids": ["VACF70388DD"],
        "website": "https://www.mirashowers.co.uk/about-us/careers",
        "seed_name": "Kohler Mira Limited",
    },
    {
        "ids": ["VAC7AADB831"],
        "website": "https://wiseorigin.co.uk",
        "seed_name": "Wise Origin",
    },
    {
        "ids": ["VAC844BC48E"],
        "website": "https://careers.lifetimegroup.org",
        "seed_name": "Lifetime Training Group Limited",
    },
    {
        "ids": ["VAC14A2F5B5"],
        "website": "https://www.listers.co.uk/careers",
        "seed_name": "Listers Group Limited",
    },
    {
        "ids": ["VAC861BB040"],
        "website": "https://lawexpress.co.uk",
        "seed_name": "Law Express",
    },
    {
        "ids": ["VAC9D9AC1FD"],
        "website": "https://www.leonardcurtis.co.uk/careers",
        "seed_name": "Leonard Curtis",
    },
    {
        "ids": ["VAC61F4979F"],
        "website": "https://magnussearch.com/join-the-team",
        "seed_name": "Magnus Search Ltd",
    },
    {
        "ids": ["VACAE055E3C"],
        "website": "https://msdigital.com/category/jobs",
        "seed_name": "Mainstream Digital Ltd",
    },
    {
        "ids": ["VAC46E90FD0"],
        "website": "https://mclaughlinharveyltd.talosats-careers.com",
        "seed_name": "McLaughlin & Harvey Construction Limited",
    },
    {
        "ids": ["VAC778B08C6"],
        "website": "https://burnettandhillman.co.uk",
        "seed_name": "Messrs Burnett & Hillman",
    },
    {
        "ids": ["VAC3D1D7F0A"],
        "website": "https://careers.mitie.com/jobs/home",
        "seed_name": "Mitie Group PLC",
    },
    {
        "ids": ["VAC643E7BAA"],
        "website": "https://www.ngbailey.com/careers",
        "seed_name": "NG Bailey Group Limited",
    },
    {
        "ids": ["VAC2180442E"],
        "website": "https://northtowerconsulting.co.uk",
        "seed_name": "North Tower Consulting Limited",
    },
    {
        "ids": ["VACC7204DE5"],
        "website": "https://www.networkrail.co.uk/careers",
        "seed_name": "Network Rail",
    },
    {
        "ids": ["VACB42BB1F8"],
        "website": "https://www.oxinst.com/careers",
        "seed_name": "Oxford Instruments PLC",
    },
    {
        "ids": ["VAC07EE2048"],
        "website": "https://permali.co.uk/careers",
        "seed_name": "Permali Gloucester Limited",
    },
    {
        "ids": ["VACECDC5E27"],
        "website": "https://www.ringway.co.uk/careers",
        "seed_name": "Ringway Infrastructure Services Limited",
    },
    {
        "ids": ["VACD7881B31"],
        "website": "https://rappor.co.uk/careers",
        "seed_name": "Rappor",
    },
    {
        "ids": ["VACE0B5AAF7"],
        "website": "https://www.bristolport.co.uk/about-us/careers",
        "seed_name": "The Bristol Port Company",
        "clear": r"SHARPNESS DOCK|Sharpness Dock|Bristol Port",
        "clear_except_ids": ["VACE0B5AAF7"],
    },
    {
        "ids": ["VAC8523BBD7"],
        "website": "https://symec.co.uk",
        "seed_name": "Symec Technologies Limited",
    },
    {
        "ids": ["VAC46E7B7A5"],
        "website": "https://synoptix.co.uk/careers",
        "seed_name": "Synoptix Ltd",
    },
    {
        "ids": ["VAC70FE181D"],
        "website": "https://taranis-engineering.co.uk",
        "seed_name": "Taranis Engineering Ltd",
    },
    {
        "ids": ["VAC97CD8E61"],
        "website": "https://taylorwoodrow.com/careers",
        "seed_name": "Taylor Woodrow Infrastructure Limited",
    },
    {
        "ids": ["VACBF437508"],
        "website": "https://www.thameswater.co.uk/careers",
        "seed_name": "Thames Water Utilities Limited",
    },
    {
        "ids": ["VAC96F18408"],
        "website": "https://www.thebestconnection.co.uk/jobs",
        "seed_name": "The Best Connection Group Limited",
    },
    {
        "ids": ["VACC8DE8944"],
        "website": "https://toyota-forklifts.co.uk/about-toyota/careers",
        "seed_name": "Toyota Material Handling UK Limited",
    },
    {
        "ids": ["VAC19C3F6C6"],
        "website": "https://uk.tricel.eu/careers",
        "seed_name": "Tricel (Weston) Limited",
    },
    {
        "ids": ["VACBE05D6C2"],
        "website": "https://tweenhills.com/contact-us",
        "seed_name": "Tweenhills Farm & Stud Ltd",
    },
    {
        "ids": ["VACC003AA8D"],
        "website": "https://newent.gloucs.sch.uk/vacancies",
        "seed_name": "Newent Community School & Sixth Form Centre",
    },
    {
        "ids": ["VACE0C7A6BA"],
        "website": "https://www.gov.uk/government/organisations/planning-inspectorate/about/recruitment",
        "seed_name": "Planning Inspectorate",
    },
    {
        "ids": ["VAC70D63606"],
        "website": "https://www.nationaltrustjobs.org.uk",
        "seed_name": "The National Trust",
    },
    {
        "ids": ["VACD8D150AD"],
        "website": "https://littlegarden.co.uk/careers",
        "seed_name": "Little Garden Day Nurseries Limited",
    },
    {
        "ids": ["VACF3C3B176"],
        "website": "https://nurseryvillage.com/careers",
        "seed_name": "Nursery Village Ltd",
        "clear": r"Nursery Village -",
        "clear_except_ids": ["VACF3C3B176"],
    },
    # --- Batch 4/5 consolidations (clear branches; keep existing parent seed) ---
    {
        "ids": ["GLC219", "VAC9FD06A87"],
        "website": "https://www.mbcareersandjobs.com",
        "seed_name": "Mitchells & Butlers Leisure Retail Limited",
        "clear": r"Mitchells|& Butlers|Miller and Carter|Harvester -|Brassmills|Botanist|Toby Carvery|O'Neill's -|Three Brooks|Browns Restaurant",
        "clear_except_ids": ["GLC219", "VAC9FD06A87"],
    },
    {
        "ids": ["GLC023", "VAC1B9F597D"],
        "website": "https://jobs.greeneking.co.uk",
        "seed_name": "Greene King Retail Services Limited",
        "clear": r"Greene King|Henbury - Bristol|Brimsham Park|Little Harp|Old Manse Hotel|Old Manor Inn|Royal Oak \(Bishops Cleeve\)|Royal George|Turnpike",
        "clear_except_ids": ["GLC023", "VAC1B9F597D"],
    },
    # --- Batch 6 ---
    {
        "ids": ["VAC464EF9CA"],
        "website": "https://accxel.co.uk/careers-in-construction",
        "seed_name": "Accxel Limited",
    },
    {
        "ids": ["VAC258C2A26"],
        "website": "https://albright-ip.co.uk/careers",
        "seed_name": "Albright IP Limited",
    },
    {
        "ids": ["VAC6DE3481F"],
        "website": "https://careers.aramark.com",
        "seed_name": "Aramark Limited",
    },
    {
        "ids": ["GLC400", "VACDFCC5CDD"],
        "website": "https://careers.diy.com",
        "seed_name": "B&Q",
        "clear": r"B&Q|B & Q PLC",
        "clear_except_ids": ["GLC400", "VACDFCC5CDD"],
    },
    {
        "ids": ["GLC377", "VACC3C74357"],
        "website": "https://careers.bam.co.uk",
        "seed_name": "BAM Construct UK Limited",
        "clear": r"BAM CONSTRUCT|BAM NUTTALL",
        "clear_except_ids": ["GLC377", "VACC3C74357"],
    },
    {
        "ids": ["VACF96AC5EC"],
        "website": "https://brayandslaughter.co.uk/careers",
        "seed_name": "Bray & Slaughter",
    },
    {
        "ids": ["VAC79BC0D8C"],
        "website": "https://broxton.com/careers",
        "seed_name": "Broxton Industries Ltd",
    },
    {
        "ids": ["VACBFDD934B"],
        "website": "https://bytesdigital.co.uk",
        "seed_name": "Bytes Digital Limited",
    },
    {
        "ids": ["VAC65C1B6AD"],
        "website": "https://carbase.co.uk/careers",
        "seed_name": "Carbase",
    },
    {
        "ids": ["VAC7EFC94F1"],
        "website": "https://careers.brambles.com",
        "seed_name": "CHEP UK Limited",
    },
    {
        "ids": ["VAC3E7A9743"],
        "website": "https://cirencester-friendly.co.uk/about-us/careers",
        "seed_name": "Cirencester Friendly Society Ltd",
    },
    {
        "ids": ["VAC6C998DFB"],
        "website": "https://cotswoldcollections.com/careers",
        "seed_name": "Cotswold Collections Ltd",
    },
    {
        "ids": ["VAC60F1D5F0"],
        "website": "https://ctskills.co.uk/careers",
        "seed_name": "CT Skills",
    },
    {
        "ids": ["VAC35315121"],
        "website": "https://careers.yeovalley.co.uk",
        "seed_name": "Yeo Valley Farms",
        "clear": r"YEO VALLEY|Yeo Valley",
        "clear_except_ids": ["VAC35315121"],
    },
    {
        "ids": ["VACEC903532"],
        "website": "https://ashleymanorprep.co.uk",
        "seed_name": "Ashley Manor Preparatory School",
    },
    {
        "ids": ["VAC4F566A5E"],
        "website": "https://aspirefoundation.org.uk/vacancies",
        "seed_name": "Aspire Foundation",
    },
    {
        "ids": ["VAC835F6A2D"],
        "website": "https://bdp.org.uk/jobs",
        "seed_name": "Bristol Drugs Project Ltd",
    },
    {
        "ids": ["VACBFD83618"],
        "website": "https://bs3community.org.uk/work-with-us",
        "seed_name": "BS3 Community Development",
    },
    {
        "ids": ["VAC1B41673C"],
        "website": "https://battledown.org.uk",
        "seed_name": "Battledown Centre for Children and Families",
    },
    {
        "ids": ["VAC1A7EC391"],
        "website": "https://careers.bromford.co.uk",
        "seed_name": "Bromford Housing Group Ltd",
    },
    {
        "ids": ["VAC81173793"],
        "website": "https://careavenues.co.uk/careers",
        "seed_name": "Care Avenues Limited",
    },
    {
        "ids": ["VAC0E9719C6"],
        "website": "https://chosenhillschool.co.uk/vacancies",
        "seed_name": "Chosen Hill School",
    },
    {
        "ids": ["VACAC1A5637"],
        "website": "https://cloverhealth.co.uk",
        "seed_name": "Clover Health and Homecare Limited",
    },
    {
        "ids": ["VACDA432EAD"],
        "website": "https://wildoakselc.co.uk",
        "seed_name": "Wild Oaks Early Learning Center Ltd",
    },
    {
        "ids": ["VAC5A77451E"],
        "website": "https://busybeeschildcare.co.uk/careers",
        "seed_name": "Busy Bees Day Nurseries",
        "clear": r"Busy Bees|BUSY BEES",
        "clear_except_ids": ["VAC5A77451E"],
    },
    {
        "ids": ["VAC95B007F1"],
        "website": "https://brightstarsnurseries.co.uk/careers",
        "seed_name": "Bright Stars Nurseries",
        "clear": r"Charlton Nursery|Bright Stars",
        "clear_except_ids": ["VAC95B007F1"],
    },
    {
        "ids": [],
        "website": "https://everyoneactive.com/careers",
        "seed_name": "Everyone Active",
        "clear": r"\(SLM\)|Horfield Leisure Centre|Royston Leisure Centre",
        "clear_except_ids": [],
    },
    # --- Batch 7 ---
    {
        "ids": ["VAC893EA343"],
        "website": "https://citywestcommercials.co.uk/careers",
        "seed_name": "City West Commercials Limited",
        "clear": r"City West Commercials",
        "clear_except_ids": ["VAC893EA343"],
    },
    {
        "ids": ["VACEF6D1510"],
        "website": "https://cornwallglass.co.uk/about-us/join-us",
        "seed_name": "Cornwall Glass & Glazing Limited",
    },
    {
        "ids": ["GLC403", "VAC8E7EA5B7"],
        "website": "https://careers.dalkia.co.uk",
        "seed_name": "Dalkia Facilities Limited",
        "clear": r"Dalkia|IMTECH ENGINEERING",
        "clear_except_ids": ["GLC403", "VAC8E7EA5B7"],
    },
    {
        "ids": ["VACB6C0D82A"],
        "website": "https://dbpixelhouse.com/careers",
        "seed_name": "DBpixelhouse Limited",
    },
    {
        "ids": ["VACBB1AF88A"],
        "website": "https://digby-associates.co.uk",
        "seed_name": "Digby Associates",
    },
    {
        "ids": ["VAC5379AD1E"],
        "website": "https://diligentacareers.co.uk",
        "seed_name": "Diligenta Ltd",
    },
    {
        "ids": ["VAC19E50C5D"],
        "website": "https://drivevauxhall.co.uk/careers",
        "seed_name": "Drive Motor Retail Limited",
    },
    {
        "ids": ["VAC4EDBBC25"],
        "website": "https://dutypoint.com/careers",
        "seed_name": "Dutypoint Systems Limited",
    },
    {
        "ids": ["VAC5529A810"],
        "website": "https://edisonfordproperty.co.uk",
        "seed_name": "Edison Ford Estate Agency",
    },
    {
        "ids": ["VAC0A03E0F5"],
        "website": "https://www.edwardsvacuum.com/en-uk/join-us",
        "seed_name": "Edwards Limited",
    },
    {
        "ids": ["VACFCAF1883"],
        "website": "https://expd8.co.uk/join-the-family",
        "seed_name": "eXpd8 Limited",
    },
    {
        "ids": ["VAC79ABD2D1"],
        "website": "https://cabotswood.com",
        "seed_name": "Cabotswood & Quayside Ltd",
    },
    {
        "ids": ["VACC13C266A"],
        "website": "https://crownlettings.co.uk",
        "seed_name": "Crown Lettings",
    },
    {
        "ids": ["VAC53D9082D"],
        "website": "https://drjonesyeovil.co.uk",
        "seed_name": "D R Jones Yeovil Ltd",
    },
    {
        "ids": ["VACA4EFDF28"],
        "website": "https://donkeywellforge.co.uk",
        "seed_name": "Donkeywell Forge Ltd",
    },
    {
        "ids": ["VACADE66EF9"],
        "website": "https://ablhealth.co.uk/join-us",
        "seed_name": "ABL Health Limited",
    },
    {
        "ids": ["VAC37F7AC9B"],
        "website": "https://gch.co.uk/jobs",
        "seed_name": "Gloucester City Homes",
    },
    {
        "ids": ["VACC6942B5E"],
        "website": "https://careers.dwp.gov.uk",
        "seed_name": "Department for Work and Pensions",
    },
    {
        "ids": ["VAC3EAE08FD"],
        "website": "https://ecctis.com/careers",
        "seed_name": "Ecctis Ltd",
    },
    {
        "ids": ["VAC2880D34E"],
        "website": "https://ftcareservices.co.uk",
        "seed_name": "First Thought Care Services Ltd",
    },
    {
        "ids": ["VAC842D748A"],
        "website": "https://claremontbristol.org.uk",
        "seed_name": "Claremont and Kingsweston Schools Federation",
        "clear": r"Claremont School|Kingsweston",
        "clear_except_ids": ["VAC842D748A"],
    },
    {
        "ids": ["VACA1678718"],
        "website": "https://bananamoon-gloucester.co.uk",
        "seed_name": "BananaMoon Gloucester",
        "clear": r"BananaMoon|Banana Moon",
        "clear_except_ids": ["VACA1678718"],
    },
    {
        "ids": ["VAC803E71BA"],
        "website": "https://portmandentex.com/careers",
        "seed_name": "PortmanDentex",
        "clear": r"DENTEX CLINICAL|Dentex|PortmanDentex",
        "clear_except_ids": ["VAC803E71BA"],
    },
    {
        "ids": ["VAC1605353B"],
        "website": "https://danievanseventing.com",
        "seed_name": "Dani Evans Eventing",
    },
    # --- Batch 8 ---
    {
        "ids": ["VAC245E4FC7"],
        "website": "https://amazon.jobs/en-gb",
        "seed_name": "Amazon UK Services Ltd",
        "clear": r"AMAZON UK|Amazon UK",
        "clear_except_ids": ["VAC245E4FC7"],
    },
    {
        "ids": ["VAC727AA224"],
        "website": "https://barnett-waddingham.co.uk/careers",
        "seed_name": "Barnett Waddingham",
    },
    {
        "ids": ["VAC4698971D"],
        "website": "https://cotswoldgroup.com/careers",
        "seed_name": "Cotswold Motor Group Limited",
        "clear": r"COTSWOLD MOTOR GROUP|Cotswold Motor Group",
        "clear_except_ids": ["VAC4698971D"],
    },
    {
        "ids": ["VAC693EEA64"],
        "website": "https://des.mod.uk/careers",
        "seed_name": "Defence Equipment & Support",
        "clear": r"Defence Equipment & Support|\bDE&S\b",
        "clear_except_ids": ["VAC693EEA64"],
    },
    {
        "ids": ["VAC41F9D9CB"],
        "website": "https://trustford.co.uk/careers",
        "seed_name": "Ford Retail Limited",
        "clear": r"FORD RETAIL|TrustFord|Trust Ford",
        "clear_except_ids": ["VAC41F9D9CB"],
    },
    {
        "ids": ["VAC44542BAA"],
        "website": "https://geminiarc.co.uk/careers",
        "seed_name": "Gemini Repairs Limited",
        "clear": r"GEMINI REPAIRS|Gemini ARC|Gemini Repairs",
        "clear_except_ids": ["VAC44542BAA"],
    },
    {
        "ids": ["VAC03F99E79"],
        "website": "https://hag.co.uk/careers",
        "seed_name": "HAG Limited",
    },
    {
        "ids": ["VAC35075163"],
        "website": "https://www.hydro.com/en-GB/careers",
        "seed_name": "Hydro Building Systems UK Limited",
        "clear": r"HYDRO BUILDING SYSTEMS",
        "clear_except_ids": ["VAC35075163"],
    },
    {
        "ids": ["VAC2CB95EC8"],
        "website": "https://jobs.kuehne-nagel.com",
        "seed_name": "Kuehne+Nagel",
        "clear": r"Kuehne|KUEHNE",
        "clear_except_ids": ["VAC2CB95EC8"],
    },
    {
        "ids": ["VAC6B7FDA97"],
        "website": "https://www.mottmac.com/careers",
        "seed_name": "Mott MacDonald Limited",
        "clear": r"Mott MacDonald|MOTT MACDONALD",
        "clear_except_ids": ["VAC6B7FDA97"],
    },
    {
        "ids": ["VAC510B4052"],
        "website": "https://motusgroup.co.uk/careers",
        "seed_name": "Motus Group (UK) Limited",
        "clear": r"MOTUS GROUP|Motus Group",
        "clear_except_ids": ["VAC510B4052"],
    },
    {
        "ids": ["VACB25BE9CE"],
        "website": "https://www.osborneclarke.com/careers",
        "seed_name": "Osborne Clarke Services",
        "clear": r"Osborne Clarke|OSBORNE CLARKE",
        "clear_except_ids": ["VACB25BE9CE"],
    },
    {
        "ids": ["VAC25EF5C68"],
        "website": "https://careers.slb.com",
        "seed_name": "Schlumberger Oilfield UK Plc",
        "clear": r"Schlumberger|SCHLUMBERGER",
        "clear_except_ids": ["VAC25EF5C68"],
    },
    {
        "ids": ["VACB9690368"],
        "website": "https://vertumotors.com/careers",
        "seed_name": "Vertu Motors Plc",
        "clear": r"VERTU MOTORS|Vertu Motors|Bristol Street Motors",
        "clear_except_ids": ["VACB9690368"],
    },
    {
        "ids": ["VAC5FCB3686"],
        "website": "https://www.wsp.com/en-gb/careers",
        "seed_name": "WSP UK Limited",
        "clear": r"^WSP\b",
        "clear_except_ids": ["VAC5FCB3686"],
    },
    {
        "ids": ["VAC7A3357E6"],
        "website": "https://theatateam.co.uk",
        "seed_name": "The Apprenticeship Training Agency Ltd",
    },
    {
        "ids": ["VACD88DF33D"],
        "website": "https://firstmilitaryrecruitment.com",
        "seed_name": "First Military Recruitment",
    },
    {
        "ids": ["VAC61CCA445"],
        "website": "https://handylabels.co.uk",
        "seed_name": "Handy Brand UK Ltd",
    },
    {
        "ids": ["VAC450F7607"],
        "website": "https://humphreys.co.uk",
        "seed_name": "Humphreys & Co Solicitors",
    },
    {
        "ids": ["VACD9A78D02"],
        "website": "https://liftinggearsafety.co.uk",
        "seed_name": "Lifting Gear & Safety Ltd",
    },
    {
        "ids": ["VACB8BB066C"],
        "website": "https://picpr.com",
        "seed_name": "PIC Public Relations Ltd",
    },
    {
        "ids": ["VAC80EB2D3C"],
        "website": "https://recruitment.raf.mod.uk",
        "seed_name": "Royal Air Force",
        "clear": r"Royal Air Force",
        "clear_except_ids": ["VAC80EB2D3C"],
    },
    {
        "ids": ["VACAB71ED3B"],
        "website": "https://www.weston.ac.uk/working-for-us",
        "seed_name": "Weston College",
    },
    {
        "ids": ["VACE002EACF"],
        "website": "https://www.avonfire.gov.uk/careers",
        "seed_name": "Avon Fire Authority",
    },
    {
        "ids": ["VAC739612D8"],
        "website": "https://osjct.co.uk/careers",
        "seed_name": "The Orders of St John Care Trust",
        "clear": r"Orders of St.? John Care Trust|OSJCT",
        "clear_except_ids": ["VAC739612D8"],
    },
    {
        "ids": ["VACA08698EE"],
        "website": "https://www.sirona-cic.org.uk/work-with-us",
        "seed_name": "Sirona Care & Health C.I.C.",
        "clear": r"Sirona Care|SIRONA CARE",
        "clear_except_ids": ["VACA08698EE"],
    },
    {
        "ids": ["VACBF43DE06"],
        "website": "https://www.windmillhillcityfarm.org.uk/about-us/jobs",
        "seed_name": "Windmill Hill City Farm Ltd",
    },
    {
        "ids": ["VAC19C4EF48"],
        "website": "https://www.briarwood.bristol.sch.uk",
        "seed_name": "Briarwood Special School",
    },
    {
        "ids": ["VAC82E86344"],
        "website": "https://sandmat.uk/vacancies",
        "seed_name": "SAND Academies Trust",
        "clear": r"SAND ACADEMIES|Milestone School",
        "clear_except_ids": ["VAC82E86344"],
    },
    {
        "ids": ["VAC80A073D7"],
        "website": "https://wessexlearningtrust.co.uk/vacancies",
        "seed_name": "Wessex Learning Trust",
        "clear": r"Wessex Learning Trust|Wedmore First School|Cheddar First School",
        "clear_except_ids": ["VAC80A073D7"],
    },
    {
        "ids": ["VAC034568D9"],
        "website": "https://www.cirencester.ac.uk/about-us/jobs",
        "seed_name": "Cirencester College",
    },
    {
        "ids": ["VACE450D1A7"],
        "website": "https://nurselinehealthcare.com/join-us",
        "seed_name": "Nurseline Healthcare Ltd",
    },
    {
        "ids": ["GLC458", "VACBC648D54"],
        "website": "https://mendipvale.nhs.uk/about-us/join-the-team",
        "seed_name": "Mendip Vale Medical Practice",
        "clear": r"Mendip Vale|Yatton Surgery",
        "clear_except_ids": ["GLC458", "VACBC648D54"],
    },
    {
        "ids": ["VACA9E20E93"],
        "website": "https://happydaysnurseries.com/careers",
        "seed_name": "Happy Days South West Limited",
        "clear": r"Happy Days|HAPPY DAYS",
        "clear_except_ids": ["VACA9E20E93"],
    },
    {
        "ids": ["GLC460", "VAC38543DAB"],
        "website": "https://acornsnurseries.co.uk/careers",
        "seed_name": "Acorns Nurseries Limited",
        "clear": r"ACORNS NURSERIES|ACORNS NURSERY SCHOOL",
        "clear_except_ids": ["GLC460", "VAC38543DAB"],
    },
    {
        "ids": ["VAC88B2EC02"],
        "website": "https://careers.pizzahut.co.uk",
        "seed_name": "Pizza Hut (U.K.) Limited",
        "clear": r"PIZZA HUT|Pizza Hut",
        "clear_except_ids": ["VAC88B2EC02"],
    },
    {
        "ids": ["VAC88C147B5"],
        "website": "https://careers.haystravel.co.uk",
        "seed_name": "Hays Travel Limited",
        "clear": r"HAYS TRAVEL|Hays Travel",
        "clear_except_ids": ["VAC88C147B5"],
    },
    {
        "ids": ["VACCFB6EF5A"],
        "website": "https://careers.askitalian.co.uk",
        "seed_name": "ASK Italian",
        "clear": r"ASK Italian",
        "clear_except_ids": ["VACCFB6EF5A"],
    },
    {
        "ids": ["VAC7CB2B769"],
        "website": "https://padel4all.com",
        "seed_name": "Padel4All Limited",
    },
    # --- Batch 9 ---
    {
        "ids": ["VAC01037B9F"],
        "website": "https://abatec.co.uk",
        "seed_name": "Abatec Limited",
    },
    {
        "ids": ["VAC654A4DB5"],
        "website": "https://www.aggregate.com/careers",
        "seed_name": "Aggregate Industries UK Limited",
        "clear": r"AGGREGATE INDUSTRIES",
        "clear_except_ids": ["VAC654A4DB5"],
    },
    {
        "ids": ["VACAE3F085B"],
        "website": "https://www.amey.co.uk/careers",
        "seed_name": "Amey Services Limited",
        "clear": r"^AMEY\b|^Amey\b",
        "clear_except_ids": ["VACAE3F085B"],
    },
    {
        "ids": ["VAC0112F08D"],
        "website": "https://aceuk.com",
        "seed_name": "Asbestos Consultants Europe Limited",
    },
    {
        "ids": ["VACE496744D"],
        "website": "https://aes-ltd.com",
        "seed_name": "Avonmouth Engineering Services Ltd",
    },
    {
        "ids": ["VACB6CABD6F"],
        "website": "https://www.breedongroup.com/careers",
        "seed_name": "Breedon Group Services Limited",
        "clear": r"^BREEDON\b|^Breedon\b",
        "clear_except_ids": ["VACB6CABD6F"],
    },
    {
        "ids": ["VACFCE6A253"],
        "website": "https://chandlers.co.uk/careers",
        "seed_name": "Chandlers (Farm Equipment) Limited",
    },
    {
        "ids": ["VACBBF362EE"],
        "website": "https://careers.howdens.com",
        "seed_name": "Howden Joinery Limited",
        "clear": r"HOWDEN JOINERY|Howdens",
        "clear_except_ids": ["VACBBF362EE"],
    },
    {
        "ids": ["VACB1AE274A"],
        "website": "https://careers.kochind.com",
        "seed_name": "Invista Textiles (U.K.) Limited",
        "clear": r"INVISTA TEXTILES|^INVISTA\b",
        "clear_except_ids": ["VACB1AE274A"],
    },
    {
        "ids": ["VACE2C6517F"],
        "website": "https://isgltd.com/careers",
        "seed_name": "ISG Ltd",
    },
    {
        "ids": ["VACE93BE680"],
        "website": "https://www.kier.co.uk/careers",
        "seed_name": "Kier Group",
        "clear": r"^Kier\b|^KIER\b",
        "clear_except_ids": ["VACE93BE680"],
    },
    {
        "ids": ["VACCCCD6EED"],
        "website": "https://www.nijhuisindustries.com/careers",
        "seed_name": "Nijhuis H2OK Ltd",
        "clear": r"NIJHUIS|Nijhuis",
        "clear_except_ids": ["VACCCCD6EED"],
    },
    {
        "ids": ["VAC44E08900"],
        "website": "https://www.petitforestier.com/en-gb/careers",
        "seed_name": "Petit Forestier UK Limited",
    },
    {
        "ids": ["VAC52CAAB05"],
        "website": "https://careers.rolls-royce.com",
        "seed_name": "Rolls-Royce Plc",
        "clear": r"ROLLS-ROYCE|Rolls-Royce",
        "clear_except_ids": ["VAC52CAAB05"],
    },
    {
        "ids": ["VAC9FCD77B9"],
        "website": "https://rotamec.com/careers",
        "seed_name": "Rotamec Ltd",
    },
    {
        "ids": ["VACDBE93BDA"],
        "website": "https://www.severntrent.com/careers",
        "seed_name": "Severn Trent Plc",
        "clear": r"SEVERN TRENT|Severn Trent",
        "clear_except_ids": ["VACDBE93BDA"],
    },
    {
        "ids": ["VACA0056A30"],
        "website": "https://www.smurfitkappa.com/careers",
        "seed_name": "Smurfit Kappa UK Ltd",
        "clear": r"SMURFIT KAPPA|Smurfit Kappa",
        "clear_except_ids": ["VACA0056A30"],
    },
    {
        "ids": ["VAC5468EF7A"],
        "website": "https://www.suez.co.uk/en-gb/careers",
        "seed_name": "Suez Recycling and Recovery UK Ltd",
        "clear": r"^SUEZ\b|^Suez\b",
        "clear_except_ids": ["VAC5468EF7A"],
    },
    {
        "ids": ["VACD87870C6"],
        "website": "https://www.tetratech.com/careers",
        "seed_name": "Tetra Tech Limited",
        "clear": r"TETRA TECH|Tetra Tech",
        "clear_except_ids": ["VACD87870C6"],
    },
    {
        "ids": ["VAC60404007"],
        "website": "https://tonygee.com/careers",
        "seed_name": "Tony Gee and Partners LLP",
    },
    {
        "ids": ["VAC7D93CD2D"],
        "website": "https://careers.vinci.com",
        "seed_name": "VINCI Plc",
        "clear": r"^VINCI\b|^Vinci\b",
        "clear_except_ids": ["VAC7D93CD2D"],
    },
    {
        "ids": ["VACED6BFC77"],
        "website": "https://agilisys.co.uk/careers",
        "seed_name": "Agilisys Limited",
    },
    {
        "ids": ["VACC4F1855E"],
        "website": "https://balloonlettings.co.uk",
        "seed_name": "Balloon Letting Company Limited",
    },
    {
        "ids": ["VACCB48CF95"],
        "website": "https://blackstarsolutions.co.uk",
        "seed_name": "Blackstar Solutions Limited",
    },
    {
        "ids": ["VAC33C5A53A"],
        "website": "https://cameronballoons.co.uk",
        "seed_name": "Cameron Balloons Ltd",
    },
    {
        "ids": ["VAC9FAE109C"],
        "website": "https://castelangroup.com/careers",
        "seed_name": "Castelan Group",
    },
    {
        "ids": ["VAC6E6C7AD7"],
        "website": "https://citysprint.co.uk/careers",
        "seed_name": "CitySprint (UK) Limited",
        "clear": r"CITYSPRINT|CitySprint",
        "clear_except_ids": ["VAC6E6C7AD7"],
    },
    {
        "ids": ["VACDC72FD7B"],
        "website": "https://www.claranet.co.uk/about-us/careers",
        "seed_name": "Claranet Limited",
    },
    {
        "ids": ["VACF4321DF6"],
        "website": "https://www.compass-group.co.uk/careers",
        "seed_name": "Compass Group UK and Ireland",
        "clear": r"COMPASS GROUP|Compass Group",
        "clear_except_ids": ["VACF4321DF6"],
    },
    {
        "ids": ["VAC9A41EC30"],
        "website": "https://lakesshoweringspaces.com",
        "seed_name": "Lakes Bathrooms Ltd",
    },
    {
        "ids": ["VACCC74741D"],
        "website": "https://markerstudygroup.com/careers",
        "seed_name": "Markerstudy Limited",
        "clear": r"MARKERSTUDY|Markerstudy",
        "clear_except_ids": ["VACCC74741D"],
    },
    {
        "ids": ["VAC193F6950"],
        "website": "https://careers.motabilityoperations.co.uk",
        "seed_name": "Motability Operations Limited",
        "clear": r"MOTABILITY|Motability",
        "clear_except_ids": ["VAC193F6950"],
    },
    {
        "ids": ["VACF9230443"],
        "website": "https://nasaumbrella.com",
        "seed_name": "NASA Umbrella Ltd",
    },
    {
        "ids": ["VAC0C23A8BF"],
        "website": "https://careers.nokia.com",
        "seed_name": "Nokia UK Limited",
        "clear": r"^Nokia\b|^NOKIA\b",
        "clear_except_ids": ["VAC0C23A8BF"],
    },
    {
        "ids": ["VAC0048D05B"],
        "website": "https://oconnellsproperty.co.uk",
        "seed_name": "O'Connells Property Agents",
    },
    {
        "ids": ["VAC50605917"],
        "website": "https://parkinsurance.co.uk",
        "seed_name": "Park Insurance Services",
    },
    {
        "ids": ["VAC74EC6111"],
        "website": "https://portlandbrown.com/careers",
        "seed_name": "Portland Brown Ltd",
    },
    {
        "ids": ["VAC6ABB515E"],
        "website": "https://careers.rac.co.uk",
        "seed_name": "RAC Motoring Services",
        "clear": r"^RAC MOTORING|^RAC\b",
        "clear_except_ids": ["VAC6ABB515E"],
    },
    {
        "ids": ["VACE7D29356"],
        "website": "https://redrhinoresourcing.co.uk",
        "seed_name": "Red Rhino Resourcing Limited",
    },
    {
        "ids": ["VACA1A5C130"],
        "website": "https://southwestupholstery.co.uk",
        "seed_name": "Southwest Upholstery Limited",
    },
    {
        "ids": ["VACB44587E3"],
        "website": "https://sovereignfireandsecurity.co.uk",
        "seed_name": "Sovereign Fire & Security Ltd",
    },
    {
        "ids": ["VAC64C9042A"],
        "website": "https://steer.co.uk/careers",
        "seed_name": "Steer Automotive Group Limited",
        "clear": r"STEER AUTOMOTIVE|Steer Automotive",
        "clear_except_ids": ["VAC64C9042A"],
    },
    {
        "ids": ["VACDC87616C"],
        "website": "https://www.sytner.co.uk/careers",
        "seed_name": "Sytner Group Limited",
        "clear": r"Sytner|SYTNER|Mercedes-Benz of Cheltenham",
        "clear_except_ids": ["VACDC87616C"],
    },
    {
        "ids": ["VAC4433C9BB"],
        "website": "https://careers.unilever.com/uk",
        "seed_name": "Unilever U.K. Central Resources Limited",
        "clear": r"UNILEVER|Unilever",
        "clear_except_ids": ["VAC4433C9BB"],
    },
    {
        "ids": ["VAC84BC7EAA"],
        "website": "https://careers.vodafone.com",
        "seed_name": "Vodafone Limited",
        "clear": r"VODAFONE|Vodafone",
        "clear_except_ids": ["VAC84BC7EAA"],
    },
    {
        "ids": ["VAC3917F552"],
        "website": "https://warnerscars.co.uk",
        "seed_name": "Warners Motors Ltd",
    },
    {
        "ids": ["VACEDC2B383"],
        "website": "https://westonarc.co.uk",
        "seed_name": "Weston ARC",
    },
    {
        "ids": ["VACB8DD1B14"],
        "website": "https://westspring-it.co.uk/careers",
        "seed_name": "Westspring IT Limited",
    },
    {
        "ids": ["VACC628A39E"],
        "website": "https://www.ymca.org.uk/work-for-us",
        "seed_name": "YMCA",
        "clear": r"Y M C A|^YMCA\b",
        "clear_except_ids": ["VACC628A39E"],
    },
    {
        "ids": ["VAC03C84971"],
        "website": "https://yatetowncouncil.gov.uk",
        "seed_name": "Yate Town Council",
    },
    {
        "ids": ["GLC515", "VACBB2F2A21"],
        "website": "https://cset.co.uk/vacancies",
        "seed_name": "Castle School Education Trust",
        "clear": r"Mangotsfield School",
        "clear_except_ids": ["GLC515", "VACBB2F2A21"],
    },
    {
        "ids": ["VAC7FF6512D"],
        "website": "https://energus.co.uk",
        "seed_name": "Energus",
        "clear": r"^Energus\b",
        "clear_except_ids": ["VAC7FF6512D"],
    },
    {
        "ids": ["VACC0D181E5"],
        "website": "https://www.civil-service-careers.gov.uk/dfe",
        "seed_name": "Department for Education",
        "clear": r"DEPARTMENT FOR EDUCATION",
        "clear_except_ids": ["VACC0D181E5"],
    },
    {
        "ids": ["GLC518", "VAC79F0D8D8"],
        "website": "https://glatrust.org.uk/vacancies",
        "seed_name": "Gloucestershire Learning Alliance",
        "clear": r"Springbank Primary Academy",
        "clear_except_ids": ["GLC518", "VAC79F0D8D8"],
    },
    {
        "ids": ["VAC8ACD60AD"],
        "website": "https://olympustrust.co.uk/vacancies",
        "seed_name": "The Olympus Academy Trust",
    },
    {
        "ids": ["VAC6578A486"],
        "website": "https://paultoninfantschool.co.uk",
        "seed_name": "Paulton Infant School",
    },
    {
        "ids": ["VACBE950DD2"],
        "website": "https://torwoodhouseschool.co.uk",
        "seed_name": "Torwood House School Ltd",
    },
    {
        "ids": ["VACFCCDE943"],
        "website": "https://trh.current-vacancies.com",
        "seed_name": "Two Rivers Housing",
    },
    {
        "ids": ["VAC78871D1A"],
        "website": "https://www.gov.uk/government/organisations/voa",
        "seed_name": "Valuation Office Agency",
    },
    {
        "ids": ["VAC4A18AF8E"],
        "website": "https://bluecoatschool.co.uk",
        "seed_name": "Blue Coat Church of England School",
    },
    {
        "ids": ["VACE2385F47"],
        "website": "https://careers.bbc.co.uk",
        "seed_name": "BBC Public Service",
        "clear": r"BBC Public Service|^BBC\b",
        "clear_except_ids": ["VACE2385F47"],
    },
    {
        "ids": ["VACE49A3484"],
        "website": "https://monksparksurgery.nhs.uk",
        "seed_name": "Monks Park Surgery",
    },
    {
        "ids": ["VACE29EC70C"],
        "website": "https://armadapractice.co.uk",
        "seed_name": "Armada Family Practice",
    },
    {
        "ids": ["VAC83397EB3"],
        "website": "https://stgeorges-surgery.co.uk",
        "seed_name": "St Georges Surgery",
    },
    {
        "ids": ["VACF9429DB6"],
        "website": "https://gensmile.co.uk/careers",
        "seed_name": "Gensmile Dental Care Limited",
        "clear": r"GENSMILE|Gensmile",
        "clear_except_ids": ["VACF9429DB6"],
    },
    {
        "ids": ["VACC172372C"],
        "website": "https://wecareandrepair.org.uk",
        "seed_name": "We Care and Repair Ltd",
    },
    {
        "ids": ["VACD6F07CF0"],
        "website": "https://becketthall.co.uk",
        "seed_name": "Beckett Hall Day Nursery Ltd",
    },
    {
        "ids": ["VAC5AC3D670"],
        "website": "https://beechhousenursery.co.uk",
        "seed_name": "Beech House Nursery School Limited",
    },
    {
        "ids": ["VAC5A5A3DFF"],
        "website": "https://jackandjillpreschool.co.uk",
        "seed_name": "Jack and Jill Preschool Ltd",
    },
    {
        "ids": ["VAC0FF2DB2B"],
        "website": "https://wrigglypeeps.co.uk",
        "seed_name": "Wrigglypeeps LLP",
    },
    {
        "ids": ["VACAF58AA0A"],
        "website": "https://stgeorgepreschool.co.uk",
        "seed_name": "St George Preschool",
    },
    {
        "ids": ["VAC675CEA2D"],
        "website": "https://toyboxdaynursery.co.uk",
        "seed_name": "Toybox Day Nursery (Bristol) Limited",
    },
    {
        "ids": ["VAC789BDDF2"],
        "website": "https://aspens-services.co.uk/careers",
        "seed_name": "Aspens-Services Limited",
        "clear": r"ASPENS-SERVICES|Aspens",
        "clear_except_ids": ["VAC789BDDF2"],
    },
    {
        "ids": ["VAC9198EDFD"],
        "website": "https://waltonparkhotel.co.uk",
        "seed_name": "Walton Park Hotel",
    },
    {
        "ids": ["VACC8F2EA80"],
        "website": "https://manorbythelake.co.uk",
        "seed_name": "The Manor by the Lake Cheltenham Ltd",
    },
    {
        "ids": ["VAC6449CA9B"],
        "website": "https://careers.welcomebreak.co.uk",
        "seed_name": "Welcome Break Group Limited",
        "clear": r"WELCOME BREAK|Welcome Break",
        "clear_except_ids": ["VAC6449CA9B"],
    },
    {
        "ids": ["VAC75640989"],
        "website": "https://berwicklodge.co.uk/careers",
        "seed_name": "Berwick Lodge Limited",
    },
    {
        "ids": ["VAC65F524D3"],
        "website": "https://letsplaybristol.co.uk",
        "seed_name": "Lets Play Bristol Ltd",
    },
    {
        "ids": ["VAC5286B9E4"],
        "website": "https://jamesbhair.co.uk",
        "seed_name": "JamesB Hair",
    },
    {
        "ids": ["VACBC23D981"],
        "website": "https://cellys.co.uk",
        "seed_name": "Celly's Unisex Hair Salon",
    },
    {
        "ids": ["VACF1AE02A3"],
        "website": "https://reflectionstraining.co.uk",
        "seed_name": "Reflections Training Academy",
    },
    {
        "ids": ["VACB596DD32"],
        "website": "https://excellect.co.uk",
        "seed_name": "Excellect",
    },
    # --- Batch 10 ---
    {
        "ids": ["VACA7493036"],
        "website": "https://clarksonevans.co.uk/careers-with-clarkson-evans",
        "seed_name": "Clarkson Evans Limited",
    },
    {
        "ids": ["VACDF7279BC"],
        "website": "https://colasrail.co.uk/careers",
        "seed_name": "Colas Rail Limited",
        "clear": r"Colas Rail|^COLAS\b",
        "clear_except_ids": ["VACDF7279BC"],
    },
    {
        "ids": ["VACC481A901"],
        "website": "https://crl-uk.com/join-the-team.php",
        "seed_name": "Concrete Repairs Limited",
    },
    {
        "ids": ["VAC42CEE926"],
        "website": "https://crewandconcierge.com",
        "seed_name": "Crew & Concierge Limited",
    },
    {
        "ids": ["GLC551", "VAC4350ACAA"],
        "website": "https://www.hl.co.uk/careers",
        "seed_name": "Hargreaves Lansdown",
        "clear": r"HL RENEWALS",
        "clear_except_ids": ["GLC551", "VAC4350ACAA"],
    },
    {
        "ids": ["VAC1A1729B5"],
        "website": "https://hayesparsons.co.uk/vacancies",
        "seed_name": "Hayes Parsons Ltd",
    },
    {
        "ids": ["VACCF323DBC"],
        "website": "https://hoarelea.com/careers",
        "seed_name": "Hoare Lea LLP",
    },
    {
        "ids": ["VACE750DF48"],
        "website": "https://hub8and.co",
        "seed_name": "Hub8",
    },
    {
        "ids": ["VAC6DE37611"],
        "website": "https://www.ocs.com/uk/careers",
        "seed_name": "OCS Group",
        "clear": r"INCENTIVE FM|Incentive FM",
        "clear_except_ids": ["VAC6DE37611"],
    },
    {
        "ids": ["VACF720C4B9"],
        "website": "https://keltruck.com/careers",
        "seed_name": "Keltruck Limited",
    },
    {
        "ids": ["VACD3CE2B7C"],
        "website": "https://kctrust.co.uk/careers",
        "seed_name": "Kings Court Trust Limited",
    },
    {
        "ids": ["VACAF52A016"],
        "website": "https://lcvehiclehire.com/vacancies",
        "seed_name": "LC Vehicle Hire",
    },
    {
        "ids": ["VAC24EE7E3D"],
        "website": "https://careers.marshmclennan.com",
        "seed_name": "Marsh & McLennan Companies",
        "clear": r"Marsh & McLennan|Marshmclennan|Mercer Insurance",
        "clear_except_ids": ["VAC24EE7E3D"],
    },
    {
        "ids": ["VAC1131F770"],
        "website": "https://motofix-arc.co.uk/careers",
        "seed_name": "Motofix Accident Repair Centres Limited",
        "clear": r"MOTOFIX|Motofix",
        "clear_except_ids": ["VAC1131F770"],
    },
    {
        "ids": ["VACEBAF312E"],
        "website": "https://pibgroup.co.uk/careers",
        "seed_name": "PIB Group Services",
        "clear": r"^PIB Group|^PIB GROUP",
        "clear_except_ids": ["VACEBAF312E"],
    },
    {
        "ids": ["VACF19DF0BE"],
        "website": "https://poeton.co.uk/careers",
        "seed_name": "Poeton Industries Limited",
    },
    {
        "ids": ["VACD3D2B1F4"],
        "website": "https://www.roechling.com/careers",
        "seed_name": "Röchling Engineering Plastics",
        "clear": r"Rochling|Röchling|ROECHLING",
        "clear_except_ids": ["VACD3D2B1F4"],
    },
    {
        "ids": ["VAC10624FE9"],
        "website": "https://rskgroup.com/careers",
        "seed_name": "RSK Group Limited",
        "clear": r"^RSK Group|^RSK GROUP",
        "clear_except_ids": ["VAC10624FE9"],
    },
    {
        "ids": ["VACB1D5DC77"],
        "website": "https://simpson-associates.co.uk/careers",
        "seed_name": "Simpson Associates Consulting Ltd",
    },
    {
        "ids": ["VACA0CEB000"],
        "website": "https://www.skanska.co.uk/about-skanska/careers",
        "seed_name": "Skanska UK Plc",
        "clear": r"^SKANSKA\b|^Skanska\b",
        "clear_except_ids": ["VACA0CEB000"],
    },
    {
        "ids": ["VAC65F54C21"],
        "website": "https://space-engineering.co.uk/work-with-us",
        "seed_name": "Space Engineering Services Limited",
    },
    {
        "ids": ["VACCD01EA7D"],
        "website": "https://www.sunbeltrentals.co.uk/careers",
        "seed_name": "Sunbelt Rentals UK",
        "clear": r"Sunbelt Rentals|SUNBELT RENTALS",
        "clear_except_ids": ["VACCD01EA7D"],
    },
    {
        "ids": ["VACFDD5E70F"],
        "website": "https://tbseng.co.uk/careers",
        "seed_name": "TBS Engineering Ltd",
    },
    {
        "ids": ["VAC4BAF40DC"],
        "website": "https://thwhite.co.uk/careers",
        "seed_name": "T H White Ltd",
    },
    {
        "ids": ["VAC04F7DEC2"],
        "website": "https://bsgltd.co.uk/about/work-with-us",
        "seed_name": "The Building Safety Group Ltd",
    },
    {
        "ids": ["VAC8E395BC6"],
        "website": "https://greatbritishcards.co.uk",
        "seed_name": "The Great British Card Company",
    },
    {
        "ids": ["VACCFA5F6CA"],
        "website": "https://careers.virginmediao2.co.uk",
        "seed_name": "Virgin Media Limited",
        "clear": r"VIRGIN MEDIA|Virgin Media",
        "clear_except_ids": ["VACCFA5F6CA"],
    },
    {
        "ids": ["VACD3E9867A"],
        "website": "https://vistrycareers.co.uk",
        "seed_name": "Vistry Group",
        "clear": r"^Vistry\b|^VISTRY\b",
        "clear_except_ids": ["VACD3E9867A"],
    },
    {
        "ids": ["VAC394E2F3A"],
        "website": "https://vpplc.com/careers",
        "seed_name": "VP Plc",
        "clear": r"^VP PLC|Brandon Hire",
        "clear_except_ids": ["VAC394E2F3A"],
    },
    {
        "ids": ["VACABD5BEA7"],
        "website": "https://careers.warburtons.co.uk",
        "seed_name": "Warburtons Limited",
        "clear": r"WARBURTONS|Warburtons",
        "clear_except_ids": ["VACABD5BEA7"],
    },
    {
        "ids": ["VAC577C8A53"],
        "website": "https://www.yunextraffic.com/uk/en/careers",
        "seed_name": "Yunex Limited",
        "clear": r"^YUNEX\b|^Yunex\b",
        "clear_except_ids": ["VAC577C8A53"],
    },
    {
        "ids": ["VAC2363DC17"],
        "website": "https://gillespiebs.co.uk",
        "seed_name": "Gillespie BS Limited",
    },
    {
        "ids": ["VACA845776B"],
        "website": "https://careers.arcadis.com",
        "seed_name": "Arcadis (UK) Limited",
        "clear": r"^ARCADIS\b|^Arcadis\b",
        "clear_except_ids": ["VACA845776B"],
    },
    {
        "ids": ["VACC8644BD6"],
        "website": "https://cathedralschoolstrust.org.uk/vacancies",
        "seed_name": "Cathedral Schools Trust",
        "clear": r"Cathedral Schools Trust",
        "clear_except_ids": ["VACC8644BD6"],
    },
    {
        "ids": ["VACC00C6B46"],
        "website": "https://stmichaelsbristol.org",
        "seed_name": "St Michaels Stoke Gifford PCC",
    },
    {
        "ids": ["VAC314BEA61"],
        "website": "https://stmichaelsprimary.co.uk",
        "seed_name": "St Michael's Primary School",
    },
    {
        "ids": ["VAC52CE779E"],
        "website": "https://www.gloucester.gov.uk/jobs-and-careers",
        "seed_name": "Gloucester City Council",
    },
    {
        "ids": ["VACBAA03226"],
        "website": "https://careers.nationalhighways.co.uk",
        "seed_name": "National Highways",
        "clear": r"National Highways",
        "clear_except_ids": ["VACBAA03226"],
    },
    {
        "ids": ["VAC1AC3DA46"],
        "website": "https://www.nhsbt.nhs.uk/careers",
        "seed_name": "NHS Blood and Transplant",
        "clear": r"NHS Blood and Transplant",
        "clear_except_ids": ["VAC1AC3DA46"],
    },
    {
        "ids": ["VACBDF02DC6"],
        "website": "https://environmentagencycareers.co.uk",
        "seed_name": "The Environment Agency",
        "clear": r"Environment Agency",
        "clear_except_ids": ["VACBDF02DC6"],
    },
    {
        "ids": ["VAC6CA559CF"],
        "website": "https://evergreenprimary.academy",
        "seed_name": "Evergreen Primary Academy",
    },
    {
        "ids": ["VACCA50A49D"],
        "website": "https://oldmixon.n-somerset.sch.uk",
        "seed_name": "Oldmixon Primary School",
    },
    {
        "ids": ["VAC02B8E790"],
        "website": "https://conistonmedicalpractice.nhs.uk",
        "seed_name": "Coniston Surgery",
    },
    {
        "ids": ["VAC1D44249F"],
        "website": "https://flexycare.co.uk",
        "seed_name": "Flexy Care Limited",
    },
    {
        "ids": ["VACFB0D8968"],
        "website": "https://milestonestrust.org.uk/work-for-us",
        "seed_name": "Milestones Trust",
        "clear": r"Milestones Trust",
        "clear_except_ids": ["VACFB0D8968"],
    },
    {
        "ids": ["VAC35340E9E"],
        "website": "https://nazarethcare.co.uk",
        "seed_name": "Nazareth Care Charitable Trust",
    },
    {
        "ids": ["VAC9674CBF6"],
        "website": "https://accessyourcare.co.uk",
        "seed_name": "Access Your Care Limited",
    },
    {
        "ids": ["VACE96C0547"],
        "website": "https://follyfarmdaynursery.co.uk",
        "seed_name": "Folly Farm Day Nursery Limited",
    },
    {
        "ids": ["VAC1E2A006B"],
        "website": "https://myohana.co.uk/careers",
        "seed_name": "My Ohana Day Nursery",
    },
    {
        "ids": ["VAC977B428E"],
        "website": "https://olvestonpreschool.co.uk",
        "seed_name": "Olveston Pre-School",
    },
    {
        "ids": ["VACBE977229"],
        "website": "https://nottinghilldaynursery.co.uk",
        "seed_name": "Notting Hill Day Nursery",
    },
    {
        "ids": ["VACF109B7F6"],
        "website": "https://playstationnursery.co.uk",
        "seed_name": "Play Station Nursery Ltd",
    },
    {
        "ids": ["VAC5A4A3FA4"],
        "website": "https://gooseberrybushnursery.co.uk",
        "seed_name": "The Gooseberry Bush Day Nursery Ltd",
    },
    {
        "ids": ["VACAD9F5C10"],
        "website": "https://jobs.cote.co.uk",
        "seed_name": "Côte Restaurant Group Ltd",
        "clear": r"COTE RESTAURANT|Cote Restaurant",
        "clear_except_ids": ["VACAD9F5C10"],
    },
    {
        "ids": ["VAC7384915B"],
        "website": "https://savers.jobs",
        "seed_name": "Savers",
        "clear": r"^Savers\b",
        "clear_except_ids": ["VAC7384915B"],
    },
    {
        "ids": ["VAC82700B2A"],
        "website": "https://peacocks.co.uk/careers",
        "seed_name": "Peacocks",
        "clear": r"^Peacocks\b",
        "clear_except_ids": ["VAC82700B2A"],
    },
    {
        "ids": ["VAC5265D9FE"],
        "website": "https://correstaurant.com",
        "seed_name": "Cor Restaurant Limited",
    },
    {
        "ids": ["VAC99D63969"],
        "website": "https://latonahotels.co.uk",
        "seed_name": "Latona Leisure Ltd",
    },
    {
        "ids": ["VAC7CD193BD"],
        "website": "https://seasonandtaste.co.uk",
        "seed_name": "Season and Taste Limited",
    },
    {
        "ids": ["VAC946C564A"],
        "website": "https://steakoftheart.co.uk",
        "seed_name": "Steak of the Art Ltd",
    },
    {
        "ids": ["VAC540D9A8C"],
        "website": "https://thegablesbristol.co.uk",
        "seed_name": "The Gables Hotel Ltd",
    },
    {
        "ids": ["VAC51386727"],
        "website": "https://phsports.co.uk",
        "seed_name": "P H Sport Coaching Ltd",
    },
    # --- Batch 11 ---
    {
        "ids": ["VACBA5337E2"],
        "website": "https://augertorque.com/about-us/careers",
        "seed_name": "Auger Torque Europe Ltd",
    },
    {
        "ids": ["VAC3637C73B"],
        "website": "https://bellwaycareers.co.uk/careers",
        "seed_name": "Bellway Homes Limited",
        "clear": r"BELLWAY HOMES|Bellway Homes",
        "clear_except_ids": ["VAC3637C73B"],
    },
    {
        "ids": ["VAC2A46664F"],
        "website": "https://cms.law/en/gbr/cms-job-opportunities",
        "seed_name": "CMS Cameron McKenna Nabarro Olswang LLP",
    },
    {
        "ids": ["VAC9F497514"],
        "website": "https://careers.enterprise.co.uk",
        "seed_name": "Enterprise Rent-A-Car UK Limited",
        "clear": r"ENTERPRISE RENT-A-CAR|Enterprise Rent-A-Car",
        "clear_except_ids": ["VAC9F497514"],
    },
    {
        "ids": ["VAC77CC8758"],
        "website": "https://filedynamics.co.uk/careers",
        "seed_name": "File Dynamics Limited",
    },
    {
        "ids": ["VACD8E60D11"],
        "website": "https://framatome.com/en/jobseekers",
        "seed_name": "Framatome UK Nuclear Services Limited",
        "clear": r"^FRAMATOME\b|^Framatome\b",
        "clear_except_ids": ["VACD8E60D11"],
    },
    {
        "ids": ["VAC5337AA67"],
        "website": "https://fusionpeople.com",
        "seed_name": "Fusion People Limited",
    },
    {
        "ids": ["VACF9EA640E"],
        "website": "https://careers.greencore.com/jobs",
        "seed_name": "Greencore Foods Limited",
        "clear": r"GREENCORE FOODS|Greencore Foods",
        "clear_except_ids": ["VACF9EA640E"],
    },
    {
        "ids": ["VAC932FFD78"],
        "website": "https://hovis.co.uk/careers",
        "seed_name": "Hovis Limited",
        "clear": r"^HOVIS\b|^Hovis\b",
        "clear_except_ids": ["VAC932FFD78"],
    },
    {
        "ids": ["VAC720876E8"],
        "website": "https://intequal.co.uk",
        "seed_name": "Intequal",
        "clear": r"^Intequal\b",
        "clear_except_ids": ["VAC720876E8"],
    },
    {
        "ids": ["VACF6920D5D"],
        "website": "https://inviron.co.uk/careers",
        "seed_name": "Inviron",
    },
    {
        "ids": ["VAC33DEB2DD"],
        "website": "https://jbaconsulting.com/careers",
        "seed_name": "JBA Consulting",
    },
    {
        "ids": ["VACB71DEBD7"],
        "website": "https://kallidus.com/careers",
        "seed_name": "Kallidus Limited",
    },
    {
        "ids": ["VAC979E0DC7"],
        "website": "https://careers.l3harris.com",
        "seed_name": "L3Harris",
        "clear": r"L3Harris|L3HARRIS",
        "clear_except_ids": ["VAC979E0DC7"],
    },
    {
        "ids": ["VAC4792FF94"],
        "website": "https://careers.uk.leonardo.com",
        "seed_name": "Leonardo MW Ltd",
        "clear": r"^LEONARDO MW|^Leonardo MW|^LEONARDO\b",
        "clear_except_ids": ["VAC4792FF94"],
    },
    {
        "ids": ["VAC81A216B5"],
        "website": "https://lornestewart.co.uk/careers",
        "seed_name": "Lorne Stewart Plc",
    },
    {
        "ids": ["VAC20AE0184"],
        "website": "https://mbdacareers.co.uk",
        "seed_name": "MBDA UK Limited",
        "clear": r"^MBDA\b",
        "clear_except_ids": ["VAC20AE0184"],
    },
    {
        "ids": ["VAC1EB2C5F6"],
        "website": "https://micheldevergroup.co.uk/current-vacancies",
        "seed_name": "Micheldever Tyre Services Limited",
        "clear": r"MICHELDEVER|Micheldever",
        "clear_except_ids": ["VAC1EB2C5F6"],
    },
    {
        "ids": ["VAC4ECF3C3D"],
        "website": "https://refusevehiclesolutions.co.uk/careers",
        "seed_name": "Refuse Vehicle Solutions Limited",
    },
    {
        "ids": ["VAC13981926"],
        "website": "https://sapphirevs.com/careers",
        "seed_name": "Sapphire Vehicle Services Limited",
    },
    {
        "ids": ["VAC4F29D190"],
        "website": "https://telent.com/careers",
        "seed_name": "Telent",
        "clear": r"^Telent\b|^TELENT\b",
        "clear_except_ids": ["VAC4F29D190"],
    },
    {
        "ids": ["VAC1A7B8F08"],
        "website": "https://wealthclub.co.uk/careers",
        "seed_name": "Wealth Club Limited",
    },
    {
        "ids": ["VAC5DF055F7"],
        "website": "https://bristol247.com/jobs",
        "seed_name": "Bristol 24/7 CIC",
    },
    {
        "ids": ["VACAE64B8A1"],
        "website": "https://fdworks.co.uk",
        "seed_name": "FD Works Limited",
    },
    {
        "ids": ["VACE500A085", "VACF2851624"],
        "website": "https://ipeco.com/careers",
        "seed_name": "Ipeco Holdings Ltd",
        "clear": r"Ipeco|IPECO",
        "clear_except_ids": ["VACE500A085", "VACF2851624"],
    },
    {
        "ids": ["VACD0D21F79"],
        "website": "https://star-legal.co.uk/careers",
        "seed_name": "Star Legal Limited",
    },
    {
        "ids": ["VAC8FEE031B"],
        "website": "https://touts.co.uk",
        "seed_name": "Tout Ltd",
    },
    {
        "ids": ["VAC1771E9B9"],
        "website": "https://cheltenham.gov.uk/jobs",
        "seed_name": "Cheltenham Borough Council",
    },
    {
        "ids": ["VACEC3F1447"],
        "website": "https://belmont.gloucs.sch.uk",
        "seed_name": "Belmont Special School",
    },
    {
        "ids": ["VAC388BBFFA"],
        "website": "https://heartoftheforest.gloucs.sch.uk",
        "seed_name": "Heart of the Forest Community Special School",
    },
    {
        "ids": ["VAC7898A0E7"],
        "website": "https://ststephensinf.org.uk",
        "seed_name": "St Stephen's Infant School",
    },
    {
        "ids": ["VAC93452FD7"],
        "website": "https://theplt.org.uk/page/?title=Careers&pid=23",
        "seed_name": "The Priory Learning Trust",
    },
    {
        "ids": ["VACA394FCDF"],
        "website": "https://wheatfieldprimary.com",
        "seed_name": "Wheatfield Primary School",
    },
    {
        "ids": ["VAC9AD6FA3C"],
        "website": "https://iopjobs.org",
        "seed_name": "Institute of Physics",
        "clear": r"Institute of Physics|INSTITUTE OF PHYSICS",
        "clear_except_ids": ["VAC9AD6FA3C"],
    },
    {
        "ids": ["VAC17E3B7AD"],
        "website": "https://thedoor.org.uk/jobs",
        "seed_name": "The Door Youth Project",
    },
    {
        "ids": ["VACDAB3D9A0"],
        "website": "https://averyhealthcare.co.uk/careers",
        "seed_name": "Avery Healthcare",
        "clear": r"AVERY CARE|Avery Care|AVERY HOMES|Avery Homes",
        "clear_except_ids": ["VACDAB3D9A0"],
    },
    {
        "ids": ["VAC2A7185D2"],
        "website": "https://caringstaffsolutions.co.uk",
        "seed_name": "Caring Staff Solutions Ltd",
    },
    {
        "ids": ["VACBE7DA7F6"],
        "website": "https://choicecaregroup.com/careers",
        "seed_name": "Choice Care Group",
        "clear": r"Choice Care Group|COMMUNITY HOMES OF INTENSIVE CARE",
        "clear_except_ids": ["VACBE7DA7F6"],
    },
    {
        "ids": ["VAC29334743"],
        "website": "https://tyntesfield.nhs.uk/vacancies",
        "seed_name": "Tyntesfield Medical Group",
    },
    {
        "ids": ["VAC0989693D"],
        "website": "https://visionexpress.com/careers",
        "seed_name": "Vision Express Limited",
        "clear": r"VISION EXPRESS|Vision Express",
        "clear_except_ids": ["VAC0989693D"],
    },
    {
        "ids": ["VAC1A7E34AA"],
        "website": "https://davidphillipsopticians.co.uk",
        "seed_name": "David Phillips Opticians",
    },
    {
        "ids": ["VACB627A051"],
        "website": "https://earlybirdsnursery.co.uk",
        "seed_name": "Early Birds Nursery",
        "clear": r"Early Birds",
        "clear_except_ids": ["VACB627A051"],
    },
    {
        "ids": ["VAC8916D320"],
        "website": "https://jobs.familyfirstnurseries.co.uk/jobs",
        "seed_name": "Family First Nurseries",
        "clear": r"Family First",
        "clear_except_ids": ["VAC8916D320"],
    },
    {
        "ids": ["VACC8856CF3"],
        "website": "https://halley.uwe.ac.uk/family-tree-nursery",
        "seed_name": "Family Tree Nursery (UWE) Ltd",
    },
    {
        "ids": ["VACC6206AC0"],
        "website": "https://thebristolmontessori.co.uk",
        "seed_name": "The Bristol Montessori",
    },
    {
        "ids": ["VACC42FB16E"],
        "website": "https://tiddlersdaynursery.co.uk",
        "seed_name": "Tiddlers Day Nursery Ltd",
    },
    {
        "ids": ["VAC01372D53"],
        "website": "https://wintonhousenursery.co.uk",
        "seed_name": "Winton House Day Nursery",
    },
    # --- Batch 12 (education / health / childcare / hospitality slice) ---
    {
        "ids": ["VACBBA54206"],
        "website": "https://backwellschool.net/vacancies",
        "seed_name": "Lighthouse Schools Partnership",
        "clear": r"BACKWELL SCHOOL|Backwell School",
        "clear_except_ids": ["VACBBA54206"],
    },
    {
        "ids": ["VACE3A089E3"],
        "website": "https://barnwood-park.gloucs.sch.uk/vacancies",
        "seed_name": "Barnwood Park School",
    },
    {
        "ids": ["VACE1BCDAE3"],
        "website": "https://cheltenhamcollege.org/about-us/vacancies",
        "seed_name": "Cheltenham College",
        "clear": r"CHELTENHAM COLLEGE|Cheltenham College",
        "clear_except_ids": ["VACE1BCDAE3"],
    },
    {
        "ids": ["VAC1E44553F"],
        "website": "https://bellbarndental.co.uk",
        "seed_name": "Bell Barn Dental Practice",
        "clear": r"Bell Barn Dental",
        "clear_except_ids": ["VAC1E44553F"],
    },
    {
        "ids": ["VACB1451B5F"],
        "website": "https://birchwoodmedicalpractice.co.uk",
        "seed_name": "Birchwood Medical Practice",
    },
    {
        "ids": ["VACC22DE51C"],
        "website": "https://dentalspa25.co.uk",
        "seed_name": "DentalSpa25",
    },
    {
        "ids": ["VACB385E193"],
        "website": "https://movemore.biz/careers",
        "seed_name": "Move More",
    },
    {
        "ids": ["VAC2A8200FC"],
        "website": "https://abbottsnursery.co.uk",
        "seed_name": "Abbotts Nursery Group",
        "clear": r"Abbotts Nursery",
        "clear_except_ids": ["VAC2A8200FC"],
    },
    {
        "ids": ["VACF6727706"],
        "website": "https://cherrytreedaynursery.com",
        "seed_name": "Cherry Tree Day Nursery",
    },
    {
        "ids": ["VAC1F5EF242"],
        "website": "https://curiouscaterpillars.co.uk",
        "seed_name": "Curious Caterpillars Ltd",
    },
    {
        "ids": ["VAC40580D03"],
        "website": "https://eastharptreenursery.org",
        "seed_name": "East Harptree Nursery Preschool",
    },
    {
        "ids": ["VACD9A55339"],
        "website": "https://flyingstartnursery.co.uk",
        "seed_name": "Flying Start Nursery Ltd",
    },
    {
        "ids": ["VACDA54EC1B"],
        "website": "https://goldenvalleydaynursery.co.uk",
        "seed_name": "Golden Valley Day Nurseries Limited",
    },
    {
        "ids": ["VAC46454ED8"],
        "website": "https://greatexpectationsdaynursery.co.uk",
        "seed_name": "Great Expectations Day Nursery Limited",
    },
    {
        "ids": ["VACF1B692A4"],
        "website": "https://hugoandholly.co.uk",
        "seed_name": "Hugo and Holly Day Nursery",
    },
    {
        "ids": ["VAC333078D7"],
        "website": "https://playworld-nursery.co.uk",
        "seed_name": "Playworld Learning Centres Limited",
        "clear": r"PLAYWORLD LEARNING|Playworld",
        "clear_except_ids": ["VAC333078D7"],
    },
    {
        "ids": ["VAC750EE43A"],
        "website": "https://adventurebristol.co.uk",
        "seed_name": "Adventure Bristol",
    },
    {
        "ids": ["VAC6DAAE04F"],
        "website": "https://butcombe.com/careers",
        "seed_name": "Butcombe Brewery Limited",
        "clear": r"BUTCOMBE BREWERY|Butcombe",
        "clear_except_ids": ["VAC6DAAE04F"],
    },
    {
        "ids": ["VACFC1840A7"],
        "website": "https://farringtongolfclub.net",
        "seed_name": "Farrington Golf & Country Club Ltd",
    },
    {
        "ids": ["VAC38672B22"],
        "website": "https://hopunionbrewery.co.uk",
        "seed_name": "Hop Union Brewery Limited",
    },
    {
        "ids": ["VACAD516490"],
        "website": "https://careers.nandos.co.uk",
        "seed_name": "Nando's",
        "clear": r"Nando's|Nandos",
        "clear_except_ids": ["VACAD516490"],
    },
    # --- Batch 13 ---
    {
        "ids": ["VAC342C1EFC"],
        "website": "https://ageas.co.uk/careers",
        "seed_name": "Ageas (UK) Limited",
        "clear": r"^AGEAS\b|^Ageas\b",
        "clear_except_ids": ["VAC342C1EFC"],
    },
    {
        "ids": ["VAC80053701"],
        "website": "https://amberley-books.com",
        "seed_name": "Amberley Publishing Holdings Limited",
    },
    {
        "ids": ["VACECCFF855"],
        "website": "https://amwins.com/careers",
        "seed_name": "Amwins Global Risks International Limited",
        "clear": r"AMWINS|Amwins",
        "clear_except_ids": ["VACECCFF855"],
    },
    {
        "ids": ["VAC2D777A96"],
        "website": "https://arthurdavid.co.uk/careers",
        "seed_name": "Arthur David (Food With Service) Limited",
    },
    {
        "ids": ["VACF86A8EF4"],
        "website": "https://baesystems.com/en/careers",
        "seed_name": "BAE Systems Plc",
        "clear": r"^BAE SYSTEMS|^BAE Systems",
        "clear_except_ids": ["VACF86A8EF4"],
    },
    {
        "ids": ["VACD4E4D282"],
        "website": "https://careers.bakerhughes.com",
        "seed_name": "Baker Hughes Limited",
        "clear": r"BAKER HUGHES|Baker Hughes",
        "clear_except_ids": ["VACD4E4D282"],
    },
    {
        "ids": ["VAC62D37B67"],
        "website": "https://borgwarner.com/careers",
        "seed_name": "BorgWarner Technologies Limited",
        "clear": r"BORGWARNER|BorgWarner",
        "clear_except_ids": ["VAC62D37B67"],
    },
    {
        "ids": ["VAC72F66CB5"],
        "website": "https://briggsandforrester.co.uk/careers",
        "seed_name": "Briggs & Forrester (Holdings) Limited",
        "clear": r"BRIGGS & FORRESTER|Briggs & Forrester",
        "clear_except_ids": ["VAC72F66CB5"],
    },
    {
        "ids": ["VAC68F21BF6"],
        "website": "https://creedfoodservice.co.uk/careers",
        "seed_name": "Creed Foodservice Limited",
    },
    {
        "ids": ["VAC1F16C2B3"],
        "website": "https://daylesford.com/careers",
        "seed_name": "Daylesford Organic Limited",
        "clear": r"DAYLESFORD|Daylesford",
        "clear_except_ids": ["VAC1F16C2B3"],
    },
    {
        "ids": ["VAC7231101E"],
        "website": "https://edmundsonelectrical.co.uk/careers",
        "seed_name": "Edmundson Electrical",
        "clear": r"Edmundson Electrical|EDMUNDSON ELECTRICAL",
        "clear_except_ids": ["VAC7231101E"],
    },
    {
        "ids": ["VAC7D8AB0F5"],
        "website": "https://flowtech.co.uk/careers",
        "seed_name": "Flowtech Fluidpower PLC",
        "clear": r"Flowtech|FLOWTECH",
        "clear_except_ids": ["VAC7D8AB0F5"],
    },
    {
        "ids": ["VACDA9D235B"],
        "website": "https://hydro-int.com/en-gb/careers",
        "seed_name": "Hydro International Limited",
        "clear": r"HYDRO INTERNATIONAL|Hydro International",
        "clear_except_ids": ["VACDA9D235B"],
    },
    {
        "ids": ["VACCC31A32A"],
        "website": "https://infinigate.com/careers",
        "seed_name": "Infinigate HLD UK Limited",
        "clear": r"INFINIGATE|Infinigate",
        "clear_except_ids": ["VACCC31A32A"],
    },
    {
        "ids": ["VACBE6AC8CD"],
        "website": "https://careers.irwinmitchell.com",
        "seed_name": "Irwin Mitchell LLP",
        "clear": r"IRWIN MITCHELL|Irwin Mitchell",
        "clear_except_ids": ["VACBE6AC8CD"],
    },
    {
        "ids": ["VACDD7E3861"],
        "website": "https://isio.com/careers",
        "seed_name": "Isio",
        "clear": r"^Isio\b|^ISIO\b|ISERAN BIDCO",
        "clear_except_ids": ["VACDD7E3861"],
    },
    {
        "ids": ["VAC0375FFF1"],
        "website": "https://lockheedmartin.com/en-gb/careers.html",
        "seed_name": "Lockheed Martin UK Limited",
        "clear": r"LOCKHEED MARTIN|Lockheed Martin",
        "clear_except_ids": ["VAC0375FFF1"],
    },
    {
        "ids": ["VACA6F94661"],
        "website": "https://migso-pcubed.com/careers",
        "seed_name": "MI-GSO PCUBED",
        "clear": r"MI-GSO|MIGSO|PCUBED",
        "clear_except_ids": ["VACA6F94661"],
    },
    {
        "ids": ["VACA6E14CB5"],
        "website": "https://michelmores.com/careers",
        "seed_name": "Michelmores LLP",
    },
    {
        "ids": ["VACE9D500D6"],
        "website": "https://optimas.com/careers",
        "seed_name": "Optimas OE Solutions Ltd",
        "clear": r"^OPTIMAS\b|^Optimas\b",
        "clear_except_ids": ["VACE9D500D6"],
    },
    {
        "ids": ["VAC91A05C79"],
        "website": "https://projectstart.co.uk",
        "seed_name": "Project Start Recruitment Solutions Ltd",
    },
    {
        "ids": ["VAC932FEC9B"],
        "website": "https://prolectric.co.uk/about-us/careers",
        "seed_name": "Prolectric Services Limited",
    },
    {
        "ids": ["VAC411823A8"],
        "website": "https://randstad.co.uk/jobs",
        "seed_name": "Randstad Group UK",
        "clear": r"^RANDSTAD\b|^Randstad\b",
        "clear_except_ids": ["VAC411823A8"],
    },
    {
        "ids": ["VAC9594B6D8"],
        "website": "https://route101.com/company/careers",
        "seed_name": "Route 101 Limited",
    },
    {
        "ids": ["VACB2F2A3DF"],
        "website": "https://seetec.co.uk/careers",
        "seed_name": "Seetec",
        "clear": r"^Seetec\b|^SEETEC\b",
        "clear_except_ids": ["VACB2F2A3DF"],
    },
    {
        "ids": ["VAC1FD69330"],
        "website": "https://srm.com/careers",
        "seed_name": "Sir Robert McAlpine Limited",
        "clear": r"SIR ROBERT MCALPINE|Sir Robert McAlpine",
        "clear_except_ids": ["VAC1FD69330"],
    },
    {
        "ids": ["VACE989E012"],
        "website": "https://skf.com/uk/organisation/careers",
        "seed_name": "SKF (U.K) Limited",
        "clear": r"^SKF\b",
        "clear_except_ids": ["VACE989E012"],
    },
    {
        "ids": ["VACA0806492"],
        "website": "https://star-ref.co.uk/careers",
        "seed_name": "Star Refrigeration Limited",
        "clear": r"STAR REFRIGERATION|Star Refrigeration",
        "clear_except_ids": ["VACA0806492"],
    },
    {
        "ids": ["VAC7414737C"],
        "website": "https://stroudmetal.co.uk",
        "seed_name": "Stroud Metal Co Ltd",
    },
    {
        "ids": ["VACBA3CE693"],
        "website": "https://sulzer.com/en/careers",
        "seed_name": "Sulzer Electro Mechanical Services (UK) Limited",
        "clear": r"^SULZER\b|^Sulzer\b",
        "clear_except_ids": ["VACBA3CE693"],
    },
    {
        "ids": ["VACE6B4CF86"],
        "website": "https://themortgagebrain.net",
        "seed_name": "The Mortgage Brain",
    },
    {
        "ids": ["VAC22D082F1"],
        "website": "https://primaryquest.co.uk/vacancies",
        "seed_name": "Primary Quest Multi Academy Trust",
    },
    {
        "ids": ["VAC32975691"],
        "website": "https://deanclose.org.uk/vacancies",
        "seed_name": "The Dean Close Foundation",
        "clear": r"DEAN CLOSE|Dean Close",
        "clear_except_ids": ["VAC32975691"],
    },
    {
        "ids": ["VAC743113AA"],
        "website": "https://sng.org.uk/careers",
        "seed_name": "Sovereign Network Group",
        "clear": r"Sovereign Housing Association",
        "clear_except_ids": ["VAC743113AA"],
    },
    {
        "ids": ["VACE8F7AF91"],
        "website": "https://seamillssurgery.nhs.uk",
        "seed_name": "Sea Mills Surgery",
    },
    {
        "ids": ["VAC28B5FAE6"],
        "website": "https://stokegiffordmedical.co.uk",
        "seed_name": "Stoke Gifford Medical Centre",
    },
    {
        "ids": ["VAC693DA92B"],
        "website": "https://purplechildcare.co.uk",
        "seed_name": "Purple Childcare Bristol Ltd",
        "clear": r"PURPLE CHILDCARE|Purple Childcare",
        "clear_except_ids": ["VAC693DA92B"],
    },
    {
        "ids": ["VACE709545E"],
        "website": "https://stonecroftdaynursery.co.uk",
        "seed_name": "Stonecroft Day Nursery Limited",
    },
    {
        "ids": ["VAC226FAA22"],
        "website": "https://storal.com/careers",
        "seed_name": "Storal",
        "clear": r"^Storal\b",
        "clear_except_ids": ["VAC226FAA22"],
    },
    {
        "ids": ["VACAE783CB5"],
        "website": "https://stonegatecareers.co.uk",
        "seed_name": "Stonegate Pub Company Limited",
        "clear": r"STONEGATE PUB|Stonegate Pub",
        "clear_except_ids": ["VACAE783CB5"],
    },
    {
        "ids": ["VAC0E2E1FBA"],
        "website": "https://superdrug.jobs",
        "seed_name": "Superdrug",
        "clear": r"^Superdrug\b",
        "clear_except_ids": ["VAC0E2E1FBA"],
    },
    # --- Batch 14 ---
    {
        "ids": ["VACB1456BCC"],
        "website": "https://agas.com/careers",
        "seed_name": "A-Gas (UK) Limited",
        "clear": r"^A-GAS\b|^A-Gas\b|^A GAS\b",
        "clear_except_ids": ["VACB1456BCC"],
    },
    {
        "ids": ["VAC386EEDA7"],
        "website": "https://amcor.com/careers",
        "seed_name": "Amcor Flexibles Winterbourne Limited",
        "clear": r"^AMCOR\b|^Amcor\b",
        "clear_except_ids": ["VAC386EEDA7"],
    },
    {
        "ids": ["VACE9AF91C5"],
        "website": "https://anglianhome.co.uk/careers",
        "seed_name": "Anglian Home Improvements Limited",
        "clear": r"ANGLIAN HOME IMPROVEMENTS|Anglian Home",
        "clear_except_ids": ["VACE9AF91C5"],
    },
    {
        "ids": ["VAC71D165BC"],
        "website": "https://jobs.aon.com",
        "seed_name": "Aon UK Limited",
        "clear": r"^AON UK|^Aon UK|^AON\b",
        "clear_except_ids": ["VAC71D165BC"],
    },
    {
        "ids": ["VAC0DFA13B8"],
        "website": "https://ashfords.co.uk/careers",
        "seed_name": "Ashfords LLP",
    },
    {
        "ids": ["VACCEE18E4B"],
        "website": "https://assaabloy.com/career",
        "seed_name": "Assa Abloy Limited",
        "clear": r"ASSA ABLOY|Assa Abloy",
        "clear_except_ids": ["VACCEE18E4B"],
    },
    {
        "ids": ["VAC77F23261"],
        "website": "https://attivogroup.co.uk/careers",
        "seed_name": "Attivo Group Limited",
        "clear": r"^ATTIVO\b|^Attivo\b",
        "clear_except_ids": ["VAC77F23261"],
    },
    {
        "ids": ["VACB0C7E88A"],
        "website": "https://barbon.com/careers",
        "seed_name": "Barbon Insurance Group Limited",
    },
    {
        "ids": ["VACC8CC2D24"],
        "website": "https://baylis.uk.com/careers",
        "seed_name": "Baylis (Gloucester) Limited",
        "clear": r"BAYLIS \(GLOUCESTER\)|Baylis Vauxhall|^Baylis\b",
        "clear_except_ids": ["VACC8CC2D24"],
    },
    {
        "ids": ["VAC29C5DB1C"],
        "website": "https://belldecoratinggroup.co.uk/careers",
        "seed_name": "Bell Decorating Group Limited",
        "clear": r"BELL DECORATING|Bell Decorating",
        "clear_except_ids": ["VAC29C5DB1C"],
    },
    {
        "ids": ["VACECD030DF"],
        "website": "https://bishopfleming.co.uk/careers",
        "seed_name": "Bishop Fleming LLP",
    },
    {
        "ids": ["VAC943D55FE"],
        "website": "https://broadstone.co.uk/careers",
        "seed_name": "Broadstone Corporate Benefits Limited",
        "clear": r"^BROADSTONE\b|^Broadstone\b",
        "clear_except_ids": ["VAC943D55FE"],
    },
    {
        "ids": ["VACDEBD7145"],
        "website": "https://careers.caci.co.uk",
        "seed_name": "CACI Limited",
        "clear": r"^CACI\b",
        "clear_except_ids": ["VACDEBD7145"],
    },
    {
        "ids": ["VACEB1B2470"],
        "website": "https://cpwp.com/careers",
        "seed_name": "Couch Perry Wilkes",
        "clear": r"^CPW\b",
        "clear_except_ids": ["VACEB1B2470"],
    },
    {
        "ids": ["VACAAD58502"],
        "website": "https://dallmeier.com/career",
        "seed_name": "Dallmeier Electronics UK Ltd",
    },
    {
        "ids": ["VACDB80336D"],
        "website": "https://dovetailandslate.co.uk",
        "seed_name": "Dovetail and Slate Limited",
    },
    {
        "ids": ["VAC2CB3E89B"],
        "website": "https://dwfgroup.com/en/careers",
        "seed_name": "DWF Law LLP",
        "clear": r"^DWF LAW|^DWF\b",
        "clear_except_ids": ["VAC2CB3E89B"],
    },
    {
        "ids": ["VACF8F16C9E"],
        "website": "https://tlt.com/careers",
        "seed_name": "TLT LLP",
        "clear": r"^TLT LLP|^TLT\b",
        "clear_except_ids": ["VACF8F16C9E"],
    },
    {
        "ids": ["VACCC7998E0"],
        "website": "https://torrecid.com/careers",
        "seed_name": "Torrecid UK - Surcotech Ltd",
        "clear": r"TORRECID|SURCOTECH|Surcotech",
        "clear_except_ids": ["VACCC7998E0"],
    },
    {
        "ids": ["VACB05EC321"],
        "website": "https://trelleborg.com/en/career",
        "seed_name": "Trelleborg Sealing Solutions UK Limited",
        "clear": r"TRELLEBORG|Trelleborg",
        "clear_except_ids": ["VACB05EC321"],
    },
    {
        "ids": ["VACBC4DEA7D"],
        "website": "https://walesandwesttruckandbus.co.uk/careers",
        "seed_name": "Truck and Bus Wales & West",
        "clear": r"Truck and Bus Wales",
        "clear_except_ids": ["VACBC4DEA7D"],
    },
    {
        "ids": ["VAC28CF89AB"],
        "website": "https://urbaser.co.uk/careers",
        "seed_name": "Urbaser Limited",
        "clear": r"^URBASER\b|^Urbaser\b",
        "clear_except_ids": ["VAC28CF89AB"],
    },
    {
        "ids": ["VACF80F26D5"],
        "website": "https://workman.co.uk/careers",
        "seed_name": "Workman LLP",
    },
    {
        "ids": ["VACF38A48DE"],
        "website": "https://peandsportsproject.co.uk",
        "seed_name": "The PE and Sports Project",
    },
    {
        "ids": ["VACDAC6E8CF"],
        "website": "https://wishford.co.uk/careers",
        "seed_name": "Wishford Education",
        "clear": r"Wishford Education|WISHFORD",
        "clear_except_ids": ["VACDAC6E8CF"],
    },
    {
        "ids": ["VAC5E0BE4C7"],
        "website": "https://asachelt.org/vacancies",
        "seed_name": "All Saints' Academy Cheltenham",
    },
    {
        "ids": ["VACEA27DC6F"],
        "website": "https://baytreeschool.co.uk",
        "seed_name": "Baytree Community School",
    },
    {
        "ids": ["VAC178CC936"],
        "website": "https://bibury.gloucs.sch.uk",
        "seed_name": "Bibury Primary School",
    },
    {
        "ids": ["VACED33E48E"],
        "website": "https://blackhorseprimary.org.uk",
        "seed_name": "Blackhorse Primary School",
    },
    {
        "ids": ["VACA18D1939"],
        "website": "https://bristolfreeschool.org.uk/vacancies",
        "seed_name": "Bristol Free School",
    },
    {
        "ids": ["VACFE9557A4"],
        "website": "https://churchdownschool.com",
        "seed_name": "Churchdown School Academy",
    },
    {
        "ids": ["VAC44B26F00"],
        "website": "https://cirencesterkingshill.gloucs.sch.uk",
        "seed_name": "Cirencester Kingshill School",
    },
    {
        "ids": ["VAC2E112AE3"],
        "website": "https://cirencesterprimaryschool.co.uk",
        "seed_name": "Cirencester Primary School",
    },
    {
        "ids": ["VACD9E2BE10"],
        "website": "https://culverhillschool.org.uk",
        "seed_name": "Culverhill School",
    },
    {
        "ids": ["VACC6A5FD06"],
        "website": "https://e-act.org.uk/careers",
        "seed_name": "E-ACT",
        "clear": r"^E-ACT\b",
        "clear_except_ids": ["VACC6A5FD06"],
    },
    {
        "ids": ["VACA570083E"],
        "website": "https://farringtongurneyschool.co.uk",
        "seed_name": "Farrington Gurney CE Primary School",
    },
    {
        "ids": ["VAC323ED004"],
        "website": "https://ablecare-homes.co.uk/careers",
        "seed_name": "AbleCare Homes",
        "clear": r"AbleCare Homes|ABLECARE",
        "clear_except_ids": ["VAC323ED004"],
    },
    {
        "ids": ["VACC78DE44C"],
        "website": "https://bnshealthcare.com/careers",
        "seed_name": "B & S Healthcare Ltd",
    },
    {
        "ids": ["VAC26194701"],
        "website": "https://badhampharmacy.co.uk/careers",
        "seed_name": "Badham Pharmacy Limited",
        "clear": r"BADHAM PHARMACY|Badham Pharmacy",
        "clear_except_ids": ["VAC26194701"],
    },
    {
        "ids": ["VAC592C92CE"],
        "website": "https://boots.jobs",
        "seed_name": "Boots",
        "clear": r"Boots Opticians|^Boots\b",
        "clear_except_ids": ["VAC592C92CE"],
    },
    {
        "ids": ["VAC787DC0B4"],
        "website": "https://hadwenhealth.co.uk/vacancies",
        "seed_name": "Hadwen Health",
    },
    {
        "ids": ["VAC3D53A409"],
        "website": "https://toddingtondaynursery.co.uk",
        "seed_name": "Toddington Day Nursery",
    },
    {
        "ids": ["VAC5EC863E3"],
        "website": "https://beansproutschildcare.co.uk",
        "seed_name": "Beansprouts Childcare Limited",
    },
    {
        "ids": ["VACB5856B71"],
        "website": "https://bristolchildcare.co.uk/careers",
        "seed_name": "Bristol Child Care Ltd",
        "clear": r"BRISTOL CHILD CARE|Bristol Child Care",
        "clear_except_ids": ["VACB5856B71"],
    },
    {
        "ids": ["VACD4D06B5A"],
        "website": "https://buckinghamgardensdaynursery.co.uk",
        "seed_name": "Buckingham Gardens Day Nursery Ltd",
    },
    {
        "ids": ["VACCE33045A"],
        "website": "https://southcerneyoutdoor.co.uk",
        "seed_name": "South Cerney Outdoor Limited",
    },
    {
        "ids": ["VACE54BF79B"],
        "website": "https://wolfridgealpaca.co.uk",
        "seed_name": "Wolfridge Alpaca Barn",
    },
    {
        "ids": ["VACA15BC19F"],
        "website": "https://woodhousepark.org.uk/about/jobs",
        "seed_name": "Woodhouse Park Activity Centre",
    },
    {
        "ids": ["VAC8DC1F00B"],
        "website": "https://thecliftonclub.co.uk",
        "seed_name": "The Clifton Club",
        "clear": r"CLIFTON CLUB|Clifton Club",
        "clear_except_ids": ["VAC8DC1F00B"],
    },
    {
        "ids": ["VAC9E2E421B"],
        "website": "https://careers.davidlloyd.co.uk",
        "seed_name": "David Lloyd Leisure Limited",
        "clear": r"DAVID LLOYD|David Lloyd",
        "clear_except_ids": ["VAC9E2E421B"],
    },
    {
        "ids": ["VAC5E1F7EFD"],
        "website": "https://freedom-leisure.co.uk/careers",
        "seed_name": "Freedom Leisure",
        "clear": r"Freedom Leisure",
        "clear_except_ids": ["VAC5E1F7EFD"],
    },
    # --- Batch 15 ---
    {
        "ids": ["VAC655C1B45"],
        "website": "https://genixhealthcare.com/careers",
        "seed_name": "Genix Healthcare Ltd",
        "clear": r"GENIX HEALTHCARE|Genix Healthcare",
        "clear_except_ids": ["VAC655C1B45"],
    },
    {
        "ids": ["VAC94DA4D59"],
        "website": "https://gloucestershirefa.com/about/vacancies",
        "seed_name": "Gloucestershire Football Association Limited",
    },
    {
        "ids": ["VACD379B599"],
        "website": "https://graphicpkg.com/careers",
        "seed_name": "Graphic Packaging International Limited",
        "clear": r"GRAPHIC PACKAGING|Graphic Packaging",
        "clear_except_ids": ["VACD379B599"],
    },
    {
        "ids": ["VACEB2974F4"],
        "website": "https://grundon.com/careers",
        "seed_name": "Grundon Waste Management Limited",
        "clear": r"^GRUNDON\b|^Grundon\b",
        "clear_except_ids": ["VACEB2974F4"],
    },
    {
        "ids": ["VACB1D120FE", "VAC3E5C8C8F"],
        "website": "https://halfords.careers",
        "seed_name": "Halfords",
        "clear": r"^HALFORDS\b|^Halfords\b",
        "clear_except_ids": ["VACB1D120FE", "VAC3E5C8C8F"],
    },
    {
        "ids": ["VACBB2AC0B8"],
        "website": "https://restoreplc.com/careers",
        "seed_name": "Restore PLC",
        "clear": r"HARROW GREEN|Harrow Green|^Restore PLC",
        "clear_except_ids": ["VACBB2AC0B8"],
    },
    {
        "ids": ["VACAED8E1FD"],
        "website": "https://harveynicholscareers.com",
        "seed_name": "Harvey Nichols and Company Limited",
        "clear": r"HARVEY NICHOLS|Harvey Nichols",
        "clear_except_ids": ["VACAED8E1FD"],
    },
    {
        "ids": ["VAC024F2C93"],
        "website": "https://hcltech.com/careers",
        "seed_name": "HCL Technologies UK Limited",
        "clear": r"^HCL TECHNOLOGIES|^HCL\b",
        "clear_except_ids": ["VAC024F2C93"],
    },
    {
        "ids": ["VACE8636340"],
        "website": "https://howardsgroup.co.uk/careers",
        "seed_name": "Howard Garages (Weston) Limited",
        "clear": r"HOWARD GARAGES|Howards Hyundai|^Howards\b",
        "clear_except_ids": ["VACE8636340"],
    },
    {
        "ids": ["VAC1A546E95"],
        "website": "https://howdengroup.com/careers",
        "seed_name": "Howden UK Group Limited",
        "clear": r"HOWDEN UK GROUP",
        "clear_except_ids": ["VAC1A546E95"],
    },
    {
        "ids": ["VAC51AD9C67"],
        "website": "https://jcb.com/en-gb/about/careers",
        "seed_name": "JCB",
        "clear": r"J\.C\. BAMFORD|^JCB\b",
        "clear_except_ids": ["VAC51AD9C67"],
    },
    {
        "ids": ["VAC47ACDC1C"],
        "website": "https://careers.jdsportsfashion.com",
        "seed_name": "JD Sports Fashion Plc",
        "clear": r"JD SPORTS|JD Sports",
        "clear_except_ids": ["VAC47ACDC1C"],
    },
    {
        "ids": ["VAC18337427"],
        "website": "https://jisc.ac.uk/about/working-for-us",
        "seed_name": "JISC",
        "clear": r"^JISC\b",
        "clear_except_ids": ["VAC18337427"],
    },
    {
        "ids": ["VACF577CEF2"],
        "website": "https://jungheinrich.co.uk/about-us/careers",
        "seed_name": "Jungheinrich UK Limited",
        "clear": r"JUNGHEINRICH|Jungheinrich",
        "clear_except_ids": ["VACF577CEF2"],
    },
    {
        "ids": ["VACABC17E68"],
        "website": "https://kellaway.co.uk/careers",
        "seed_name": "Kellaway Building Supplies Limited",
    },
    {
        "ids": ["VACD07F9476"],
        "website": "https://langleywellington.co.uk/careers",
        "seed_name": "Langley Wellington LLP",
    },
    {
        "ids": ["VACAADC12EE"],
        "website": "https://suntorybfe.com/careers",
        "seed_name": "Lucozade Ribena Suntory Limited",
        "clear": r"LUCOZADE RIBENA SUNTORY|Suntory Beverage",
        "clear_except_ids": ["VACAADC12EE"],
    },
    {
        "ids": ["VAC77BE12CB"],
        "website": "https://merkle.com/careers",
        "seed_name": "Merkle UK One Limited",
        "clear": r"^MERKLE\b|^Merkle\b",
        "clear_except_ids": ["VAC77BE12CB"],
    },
    {
        "ids": ["VACC73FDCB2"],
        "website": "https://networkplus.co.uk/careers",
        "seed_name": "Network Plus Services Ltd",
        "clear": r"NETWORK PLUS|Network Plus",
        "clear_except_ids": ["VACC73FDCB2"],
    },
    {
        "ids": ["VAC389F9E53"],
        "website": "https://nfumutual.co.uk/careers",
        "seed_name": "NFU Mutual",
        "clear": r"NFU Mutual|NFU MUTUAL",
        "clear_except_ids": ["VAC389F9E53"],
    },
    {
        "ids": ["VACF024C25D"],
        "website": "https://octopus.energy/careers",
        "seed_name": "Octopus Energy Services",
        "clear": r"Octopus Energy",
        "clear_except_ids": ["VACF024C25D"],
    },
    {
        "ids": ["VACD10F7D9E"],
        "website": "https://pickeringslifts.co.uk/careers",
        "seed_name": "Pickerings Europe Limited",
        "clear": r"PICKERINGS EUROPE|Pickerings",
        "clear_except_ids": ["VACD10F7D9E"],
    },
    {
        "ids": ["VACCDC82C0A"],
        "website": "https://placesforpeople.co.uk/careers",
        "seed_name": "Places for People Group Limited",
        "clear": r"PLACES FOR PEOPLE|Places for People",
        "clear_except_ids": ["VACCDC82C0A"],
    },
    {
        "ids": ["VACF9D7A212"],
        "website": "https://powerelectrics.com/careers",
        "seed_name": "Power Electrics (Bristol) Limited",
        "clear": r"POWER ELECTRICS \(BRISTOL\)|Power Electrics",
        "clear_except_ids": ["VACF9D7A212"],
    },
    {
        "ids": ["VAC93170418"],
        "website": "https://pumaenergy.com/en/careers",
        "seed_name": "Puma Energy (UK) Limited",
        "clear": r"PUMA ENERGY|Puma Energy",
        "clear_except_ids": ["VAC93170418"],
    },
    {
        "ids": ["VAC5497955C"],
        "website": "https://rygor.co.uk/careers",
        "seed_name": "Rygor Commercials",
        "clear": r"^Rygor\b|^RYGOR\b",
        "clear_except_ids": ["VAC5497955C"],
    },
    {
        "ids": ["VAC19AC6A54"],
        "website": "https://savills.co.uk/careers",
        "seed_name": "Savills (UK) Limited",
        "clear": r"^SAVILLS\b|^Savills\b",
        "clear_except_ids": ["VAC19AC6A54"],
    },
    {
        "ids": ["VAC4A0800C6"],
        "website": "https://grangefield.gloucs.sch.uk",
        "seed_name": "Grangefield School",
    },
    {
        "ids": ["VACE21DBCD3"],
        "website": "https://hannahmore.org.uk",
        "seed_name": "Hannah More Primary School",
    },
    {
        "ids": ["VAC00DF2918"],
        "website": "https://greenshawlearningtrust.co.uk/join-us",
        "seed_name": "Greenshaw Learning Trust",
        "clear": r"Holmleigh Park|Greenshaw Learning Trust",
        "clear_except_ids": ["VAC00DF2918"],
    },
    {
        "ids": ["VACEE974780"],
        "website": "https://leckhampton.gloucs.sch.uk",
        "seed_name": "Leckhampton C of E Primary School",
    },
    {
        "ids": ["VAC632ED4F8"],
        "website": "https://longlevensinfantschool.co.uk",
        "seed_name": "Longlevens Infant School",
    },
    {
        "ids": ["GLC102", "VAC3C4C367D"],
        "website": "https://nationalstar.org/jobs",
        "seed_name": "National Star Foundation",
        "clear": r"National Star College|NATIONAL STAR",
        "clear_except_ids": ["GLC102", "VAC3C4C367D"],
    },
    {
        "ids": ["VACD6978F94"],
        "website": "https://olvestonschool.co.uk",
        "seed_name": "Olveston CEVC Primary School",
    },
    {
        "ids": ["VAC8BDFBF12"],
        "website": "https://lawrencehillhealthcentre.co.uk",
        "seed_name": "Lawrence Hill Health Centre",
    },
    {
        "ids": ["VACCC5F3482"],
        "website": "https://nightingalevalleypractice.co.uk",
        "seed_name": "Nightingale Valley Practice",
    },
    {
        "ids": ["VACAF327C4E"],
        "website": "https://alliancehomes.org.uk/careers",
        "seed_name": "Alliance Homes",
        "clear": r"NSAH \(Alliance Homes\)|Alliance Homes",
        "clear_except_ids": ["VACAF327C4E"],
    },
    {
        "ids": ["VAC30EC5F36"],
        "website": "https://pierhealth.co.uk/careers",
        "seed_name": "Pier Health Group",
        "clear": r"PIER HEALTH|Pier Health",
        "clear_except_ids": ["VAC30EC5F36"],
    },
    {
        "ids": ["VAC349109C9"],
        "website": "https://nfrsa.org.uk",
        "seed_name": "National Foundation for Retired Service Animals",
    },
    {
        "ids": ["VACBCE7A6E3"],
        "website": "https://highnamdaynursery.co.uk",
        "seed_name": "Highnam Day Nursery Ltd",
    },
    {
        "ids": ["VAC4452672C"],
        "website": "https://littleapplesnursery.co.uk",
        "seed_name": "Little Apples Day Nursery",
    },
    {
        "ids": ["VACC0D8E311"],
        "website": "https://poppyseedsdaynursery.co.uk",
        "seed_name": "Poppyseeds Day Nursery Limited",
    },
    {
        "ids": ["VACF9DC2D93"],
        "website": "https://henburygolfclub.co.uk",
        "seed_name": "Henbury Golf Club",
    },
    {
        "ids": ["VAC92414A27"],
        "website": "https://jdwetherspooncareers.com",
        "seed_name": "JD Wetherspoon",
        "clear": r"J D Wetherspoon|Wetherspoon",
        "clear_except_ids": ["VAC92414A27"],
    },
    {
        "ids": ["VAC064DC7BC"],
        "website": "https://premier-education.com/careers",
        "seed_name": "Premier Education",
        "clear": r"Premier Education",
        "clear_except_ids": ["VAC064DC7BC"],
    },
]


_STOP = {"limited", "ltd", "llp", "plc", "group", "the", "and", "of", "uk", "co"}


def _tokens(name: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", name.lower()) if t not in _STOP and len(t) > 1}


def seed_names_match(a: str, b: str) -> bool:
    """Strict match: identical token sets, or shorter name's tokens all inside longer."""
    na, nb = str(a or "").strip().lower(), str(b or "").strip().lower()
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    # Avoid merging distinct orgs that share only generic tokens (nursery, council, nhs)
    if len(shorter) < 2:
        return False
    return shorter <= longer


def ensure_seed_row(
    seed: pd.DataFrame,
    *,
    name: str,
    website: str,
    town: str,
    template: pd.Series | None,
    prefer_ids: list[str],
) -> tuple[pd.DataFrame, str]:
    """Return seed + company_id for a curated parent (one row only)."""
    for cid in prefer_ids:
        hit = seed["company_id"].astype(str) == cid
        if hit.any():
            idx = seed.index[hit][0]
            seed.at[idx, "website"] = website
            return seed, cid

    for idx, row in seed.iterrows():
        if seed_names_match(str(row["name"]), name):
            seed.at[idx, "website"] = website
            return seed, str(row["company_id"])

    cid = f"GLC{max_glc_id(seed) + 1:03d}"
    cols = list(seed.columns)
    rec = {c: "" for c in cols}
    if template is not None:
        for c in cols:
            if c in template.index and c not in ("company_id", "website", "name", "source"):
                rec[c] = template[c]
    rec["company_id"] = cid
    rec["name"] = name
    rec["website"] = website
    rec["source"] = "seed"
    rec["priority_employer"] = "0"
    if town:
        rec["town"] = town
    if not str(rec.get("summary") or "").strip():
        rec["summary"] = (
            f"Local employer with recent apprenticeship vacancies. "
            f"Check {website} for current opportunities."
        )[:500]
    seed = pd.concat([seed, pd.DataFrame([rec])], ignore_index=True)
    return seed, cid


def sync_seed_into_master(master: pd.DataFrame, seed: pd.DataFrame, company_id: str) -> pd.DataFrame:
    row = seed.loc[seed["company_id"].astype(str) == company_id]
    if row.empty:
        return master
    r = row.iloc[0]
    mask = master["company_id"].astype(str) == company_id
    if mask.any():
        master.loc[mask, "website"] = r["website"]
        return master
    # append seed copy into master
    cols = list(master.columns)
    rec = {c: (r[c] if c in seed.columns else "") for c in cols}
    for c in cols:
        if c not in rec or rec[c] is None:
            rec[c] = ""
    return pd.concat([master, pd.DataFrame([rec])], ignore_index=True)


def main() -> None:
    seed = pd.read_csv(SEED, dtype=str).fillna("")
    master = pd.read_csv(MASTER, dtype=str).fillna("")

    applied = 0
    cleared = 0

    for spec in PARENTS:
        website = norm_url(spec["website"])
        if not website:
            continue
        ids = [str(x) for x in spec.get("ids") or []]
        clear_pat = spec.get("clear")
        except_ids = set(str(x) for x in spec.get("clear_except_ids") or ids)

        if clear_pat:
            mask = name_mask(master, clear_pat) & ~master["company_id"].astype(str).isin(
                except_ids
            )
            n = int(mask.sum())
            if n:
                master.loc[mask, "website"] = ""
                cleared += n
            smask = name_mask(seed, clear_pat) & ~seed["company_id"].astype(str).isin(
                except_ids
            )
            if smask.any():
                seed.loc[smask, "website"] = ""

        template = None
        for cid in ids:
            m = master["company_id"].astype(str) == cid
            if m.any():
                template = master.loc[m].iloc[0]
                applied += 1

        seed, seed_cid = ensure_seed_row(
            seed,
            name=spec["seed_name"],
            website=website,
            town=str(
                spec.get("town")
                or (template.get("town") if template is not None else "")
                or ""
            ),
            template=template,
            prefer_ids=ids,
        )
        master = sync_seed_into_master(master, seed, seed_cid)

        # One matchable org only: website lives on seed parent, not vacancy duplicates
        for cid in ids:
            if cid != seed_cid:
                m = master["company_id"].astype(str) == cid
                if m.any():
                    master.loc[m, "website"] = ""
                    cleared += int(m.sum())

    seed.to_csv(SEED, index=False)
    master.to_csv(MASTER, index=False)

    sw = (seed["website"].map(public_employer_website).astype(bool)).sum()
    mw = (master["website"].map(public_employer_website).astype(bool)).sum()
    print(f"Parents applied (id touches): {applied}")
    print(f"Branch websites cleared: {cleared}")
    print(f"Seed: {len(seed)} rows, {sw} with public website")
    print(f"Master: {len(master)} rows, {mw} with public website")


if __name__ == "__main__":
    main()

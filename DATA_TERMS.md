# Data terms

What you may do with the corpus this repository publishes, what you owe
whom, and whom to write to about a person's record. The code that produces
the corpus is MIT-licensed ([LICENSE](LICENSE)); this file is about the
data.

## Source and status

Every record is compiled from the **public candidate pages of the Lithuanian
Central Electoral Commission** (Lietuvos Respublikos vyriausioji rinkimų
komisija, VRK, <https://www.vrk.lt>): the questionnaires, asset and income
declaration extracts, private-interest declarations, campaign-finance pages
and portraits VRK publishes for every registered candidate under the
Republic of Lithuania's election law. VRK publishes them so that voters can
know who is asking for their vote; this project retains the pages as
fetched, parses them, and republishes the result in a form that can be
compared across elections.

This project claims no rights over VRK's content. The pages are VRK's; the
facts on them are what the candidates declared. What this project adds — the
selection and arrangement, the normalized layer, the cross-election
identity, the derived tables, the documentation — is what the licence below
covers.

## Licence of the compilation

The corpus — every release asset (`candidacies.csv.gz`, `campaigns.csv.gz`,
`vrk.sqlite.gz`, `vrk-corpus.sqlite.gz`, the `vrk-photos-N.sqlite` portrait
parts, `MANIFEST.json`), the record files
under `data/`, `dashboard/people.json` and the documentation describing
them — is published under the **Creative Commons Attribution 4.0
International licence (CC BY 4.0)**:
<https://creativecommons.org/licenses/by/4.0/>.

You may copy, redistribute, transform and build on it, for any purpose,
provided you attribute it. The required attribution is:

> VRK election corpus by Viešpirkiai (https://github.com/Viespirkiu-grupe/vrk),
> CC BY 4.0. Source: Lietuvos Respublikos vyriausioji rinkimų komisija
> (vrk.lt).

Name the release you used (`corpus-YYYY-MM-DD`, from `MANIFEST.json`'s
`version`) where the version matters to your result. `MANIFEST.json` carries
the same terms in machine-readable form (`license`, `dataLicense`,
`attribution`, `terms`), so they travel with the assets; the release notes
end with the attribution line.

## Personal data and removal

The corpus is a register of **people**: 113,073 candidacies of about 60,700
named persons, with birth dates, birth places, declared assets and income,
declared convictions, campaign finances and portraits, exactly as VRK
published them. It also carries third parties who never stood for election
— the spouse and children a candidate named on the questionnaire, the
family members and business partners listed in a private-interest
declaration, the treasurer and auditor of a campaign — again as VRK
published them. [docs/PERSONAL_DATA.md](docs/PERSONAL_DATA.md) is the
field-by-field inventory: who each field is about and how sensitive it is,
and which fields the public release drops.

Three things follow:

- **Reuse it as what it is: public election records.** Do not use it to
  profile or contact individuals, and do not combine it with other sources
  to derive facts about a person that VRK did not publish.
- **VRK is the source of the facts.** A record that misstates what a page
  said is a parser defect and this project's to fix; a page whose content
  is wrong is VRK's to correct, and the record will follow when the page is
  re-fetched.
- **You can ask for a record to be removed or corrected.** Open an issue at
  <https://github.com/Viespirkiu-grupe/vrk/issues>, or write to
  <viespirkiai@viespirkiai.org>, naming the election and the candidate. A
  request from the person concerned, or someone acting for them, is acted
  on in the next release: the record is dropped or corrected in the release
  assets and in `dashboard/people.json`, the retained source page is kept
  offline only, and the change is noted in the release notes. Anything
  already downloaded by others is outside this project's reach — the
  licence above permits redistribution — which is why the request is acted
  on quickly rather than debated.

## Warranty

None. The corpus is what VRK's pages said on the day they were fetched, read
by parsers that are tested but not infallible; `docs/DATASET.md` lists the
known gaps and the caveats for analysis, and every record names the page it
came from (`source.candidateSourceUrl`) so a figure can be checked against
VRK's own publication.

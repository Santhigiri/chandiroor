---
name: Bug report
about: Report incorrect Panchangam values, API errors, or other defects
title: "[Bug]: "
labels: bug
assignees: ''
---

## Describe the bug

<!-- A clear and concise description of what the bug is. -->

## Affected area

<!-- Check all that apply. -->

- [ ] Incorrect astronomical value (Thithi / Nakshatra / sunrise-sunset / Kollavarsham)
- [ ] Incorrect Santhigiri event / significant date
- [ ] Transition time wrong or missed (Thithi/Nakshatra boundary)
- [ ] API error / crash (5xx, exception)
- [ ] Wrong or unexpected response schema
- [ ] Other

## Request details

<!-- Fill in what applies. -->

- **Endpoint:** <!-- e.g. GET /api/v1/panchangam/day -->
- **Date(s) queried:** <!-- e.g. 2028-01-14 -->
- **Full request URL:** <!-- e.g. /api/v1/panchangam/day?date_str=2028-01-14 -->

## Expected value

<!-- What the correct Panchangam value should be. Cite your source: a physical Panchangam, Drik Panchang, etc. -->

- **Source of truth:** <!-- e.g. Drik Panchang, printed Santhigiri Panchangam -->

## Actual value

<!-- What the API returned. Paste the relevant part of the JSON response. -->

```json

```

## Steps to reproduce

1.
2.
3.

## Environment

- **How it's running:** <!-- local uvicorn / Docker / deployed -->
- **Commit or version:** <!-- git SHA or tag -->
- **Python version:** <!-- e.g. 3.11 -->

## Additional context

<!-- Logs (especially startup transition-miss warnings), screenshots, or anything else relevant.
     Note: values for dates outside 2021–2030 are computed live and will have empty santhigiri_significant_dates — that is expected, not a bug. -->

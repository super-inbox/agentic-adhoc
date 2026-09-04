# Grain & Glow — Store-standee whitespace delta v3

## Client decisions recorded

- Keep the approved gift box unchanged.
- Keep the current Taobao main image unchanged.
- Change only the store standee: restore the sparser whitespace treatment from the v1 standee.
- The previously removed price label must not return anywhere in the revised standee.

## Exact edit boundary

Allowed change:

1. Adjust only the store-standee whitespace/spacing to match the v1 sparse reference.

Locked and unchanged:

- Gift box, Logo, product imagery, visual-system palette, lighting, materials, copy, and hierarchy.
- Current Taobao main image and its no-price-label state.
- All approved elements outside the standee spacing regions.

## Saved-state continuity audit

The files currently available in this workspace do not match the assets referenced in the new feedback:

- `outputs/v2` contains only `change-request.md` and `verification.json`; it contains no gift-box or Taobao main-image file.
- The last available approved gift-box visual is in `outputs/v1/b-layers-in-light-premium-gift-box-logo-locked.png`.
- No Taobao main-image file exists in any version folder.
- No current store-standee file exists.
- No v1 sparse store-standee reference exists.

## Blocking input

Required to perform the delta without redesigning unrelated areas:

- The current full-resolution or editable store standee to be changed.
- The v1 sparser store-standee reference, or an editable source containing that version.

No standee, gift box, Taobao main image, Logo, price label, or visual-system element was generated or reconstructed in v3.

import assert from "node:assert/strict";
import test from "node:test";

import {
  createStructureHistory,
  createStructureSectionId,
  duplicateStructureSection,
  moveStructureSection,
  pushStructureHistory,
  redoStructureHistory,
  structureEndpoint,
  undoStructureHistory,
  validateStructureSections,
} from "./structure";

const sections = [
  { section_id: "verse", label: "Verse" },
  { section_id: "chorus", label: "Chorus" },
];

test("builds structure endpoint", () => {
  assert.equal(
    structureEndpoint("http://localhost:8000", "project-1"),
    "http://localhost:8000/api/v1/projects/project-1/structure",
  );
});

test("moves and duplicates sections while retaining the source reference", () => {
  const moved = moveStructureSection(sections, 1, -1);
  assert.deepEqual(moved.map((section) => section.section_id), ["chorus", "verse"]);
  const duplicated = duplicateStructureSection(moved, 0, "chorus-copy", "Chorus Copy");
  assert.equal(duplicated[1].source_section_id, "chorus");
  assert.equal(duplicated[1].section_id, "chorus-copy");
});

test("creates collision-free section ids", () => {
  assert.equal(createStructureSectionId(["section-abc"], "abc"), "section-abc-2");
});

test("tracks undo and redo without creating server versions", () => {
  const initial = createStructureHistory(sections);
  const changed = pushStructureHistory(initial, [{ ...sections[0], label: "Verse A" }, sections[1]]);
  assert.equal(changed.present[0].label, "Verse A");
  const undone = undoStructureHistory(changed);
  assert.equal(undone.present[0].label, "Verse");
  assert.equal(redoStructureHistory(undone).present[0].label, "Verse A");
});

test("validates labels and unique ids", () => {
  assert.equal(validateStructureSections([]), "At least one song section is required.");
  assert.equal(
    validateStructureSections([sections[0], { ...sections[1], section_id: "verse" }]),
    "Section IDs must be unique.",
  );
  assert.equal(validateStructureSections(sections), null);
});

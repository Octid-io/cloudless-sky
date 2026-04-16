const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, AlignmentType, Table, TableRow,
        TableCell, BorderStyle, WidthType } = require("docx");

const B = { style: BorderStyle.SINGLE, size: 2, color: "000000" };
const NB = { style: BorderStyle.NONE, size: 0 };
const borders = { top: B, bottom: B, left: B, right: B };
const noBorders = { top: NB, bottom: NB, left: NB, right: NB };
const F = "Arial";
const SZ = 18;

function box(text, w, bold) {
  return new TableCell({
    borders, width: { size: w, type: WidthType.DXA },
    verticalAlign: "center",
    margins: { top: 80, bottom: 80, left: 100, right: 100 },
    children: [new Paragraph({ alignment: AlignmentType.CENTER,
      spacing: { before: 40, after: 40 },
      children: [new TextRun({ text, size: SZ, font: F, bold: !!bold })]
    })]
  });
}

function blank(w) {
  return new TableCell({
    borders: noBorders, width: { size: w, type: WidthType.DXA },
    children: [new Paragraph({ children: [] })]
  });
}

function arrow(w, text) {
  return new TableCell({
    borders: noBorders, width: { size: w, type: WidthType.DXA },
    verticalAlign: "center",
    children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: text || "\u2193", size: 22, font: F })]
    })]
  });
}

function spanCell(text, subtext, bold, useBorder) {
  const kids = [new Paragraph({ alignment: AlignmentType.CENTER,
    spacing: { before: 60, after: subtext ? 20 : 60 },
    children: [new TextRun({ text, size: SZ, font: F, bold: !!bold })]
  })];
  if (subtext) kids.push(new Paragraph({ alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 60 },
    children: [new TextRun({ text: subtext, size: 16, font: F })]
  }));
  return new TableCell({
    borders: useBorder ? borders : noBorders,
    columnSpan: 3,
    width: { size: 8200, type: WidthType.DXA },
    verticalAlign: "center",
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: kids
  });
}

const W = [800, 3400, 1000, 3400, 800];

function r(c1, c2, c3, c4, c5) { return new TableRow({ children: [c1, c2, c3, c4, c5] }); }
function arrowRow() { return r(blank(W[0]), arrow(W[1]), blank(W[2]), arrow(W[3]), blank(W[4])); }

const rows = [
  // Title
  new TableRow({ children: [
    blank(W[0]),
    new TableCell({ borders: noBorders, columnSpan: 3, width: { size: W[1]+W[2]+W[3], type: WidthType.DXA },
      children: [
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 },
          children: [new TextRun({ text: "FIG. 1", bold: true, size: 24, font: F })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 },
          children: [new TextRun({ text: "Three-Mode Vocabulary Measurement Instrument", size: 20, font: F })] })
      ]
    }),
    blank(W[4])
  ]}),

  // Input
  r(blank(W[0]),
    box("100\nCANDIDATE\nIDENTIFIER SET", W[1], true),
    blank(W[2]),
    box("102\nNATURAL LANGUAGE\nDESCRIPTIONS", W[3], true),
    blank(W[4])),
  arrowRow(),

  // Panel
  new TableRow({ children: [
    blank(W[0]),
    spanCell("104 - CROSS-VENDOR LANGUAGE MODEL PANEL",
             "\u2265 3 models  |  \u2265 2 vendor lineages  |  independent measurement",
             true, true),
    blank(W[4])
  ]}),
  arrowRow(),

  // Mode 1 + Mode 3
  r(blank(W[0]),
    box("106\nMODE 1: RECOGNITION\nWITH contextual frame", W[1], true),
    blank(W[2]),
    box("112\nMODE 3: GENERATION\ncompose freely from\nvocabulary", W[3], true),
    blank(W[4])),
  arrowRow(),

  // Mode 2 + Gen Classification
  r(blank(W[0]),
    box("108\nMODE 2: RECOGNITION\nWITHOUT contextual frame", W[1], true),
    blank(W[2]),
    box("114\n5-CATEGORY\nGENERATION\nCLASSIFICATION", W[3], false),
    blank(W[4])),
  arrowRow(),

  // Classifications
  r(blank(W[0]),
    box("110\n4-CATEGORY\nDUAL-MODE DELTA\nCLASSIFICATION", W[1], false),
    blank(W[2]),
    box("116\nGRADUATED\nGENERATION\nACCESS PATHS", W[3], false),
    blank(W[4])),
  arrowRow(),

  // Reduction + Discovery
  r(blank(W[0]),
    box("118\nITERATIVE REDUCTION\n(minimum surface form\npreserving recognition)", W[1], true),
    arrow(W[2], "\u2190\u2192"),
    box("120\nDISCOVERY OUTPUTS\n(gaps, ambiguities,\npanel-preferred forms)", W[3], true),
    blank(W[4])),
  arrowRow(),

  // Output
  new TableRow({ children: [
    blank(W[0]),
    spanCell("122 - BIDIRECTIONAL VOCABULARY",
             "Recognition paths (Modes 1+2) + Generation paths (Mode 3) + Reduction",
             true, true),
    blank(W[4])
  ]}),
];

const table = new Table({
  width: { size: W.reduce((a,b) => a+b, 0), type: WidthType.DXA },
  columnWidths: W,
  rows
});

const doc = new Document({
  styles: { default: { document: { run: { font: "Arial", size: 20 } } } },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 720, bottom: 1440, left: 720 }
      }
    },
    children: [
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 },
        children: [new TextRun({ text: "1/1", bold: true, size: 20, font: "Arial" })] }),
      table
    ]
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("C:/Users/clay/Desktop/Transcripts and files for coordination/IP Current/ZTOLE-UTILITY-DRAWING-FIG1.docx", buf);
  console.log("Done: " + buf.length + " bytes");
});

const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, AlignmentType, Table, TableRow,
        TableCell, BorderStyle, WidthType, ShadingType } = require("docx");

const B = { style: BorderStyle.SINGLE, size: 2, color: "000000" };
const NB = { style: BorderStyle.NONE, size: 0 };
const borders = { top: B, bottom: B, left: B, right: B };
const noBorders = { top: NB, bottom: NB, left: NB, right: NB };
const F = "Arial";

function box(text, w, shade, bold) {
  return new TableCell({
    borders, width: { size: w, type: WidthType.DXA },
    shading: shade ? { fill: shade, type: ShadingType.CLEAR } : undefined,
    verticalAlign: "center",
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ alignment: AlignmentType.CENTER,
      spacing: { before: 40, after: 40 },
      children: [new TextRun({ text, size: 18, font: F, bold: !!bold })]
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
      children: [new TextRun({ text: text || "\u2193", size: 20, font: F })]
    })]
  });
}

function spanBox(text, subtext, shade, bold) {
  const kids = [new Paragraph({ alignment: AlignmentType.CENTER,
    spacing: { before: 60, after: subtext ? 20 : 60 },
    children: [new TextRun({ text, size: 20, font: F, bold: !!bold })]
  })];
  if (subtext) kids.push(new Paragraph({ alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 60 },
    children: [new TextRun({ text: subtext, size: 16, font: F, italics: true })]
  }));
  return new TableCell({
    borders, columnSpan: 3,
    width: { size: 8200, type: WidthType.DXA },
    shading: shade ? { fill: shade, type: ShadingType.CLEAR } : undefined,
    verticalAlign: "center",
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: kids
  });
}

// Columns: [pad=800 | left=3400 | mid=1000 | right=3400 | pad=800]
const W = [800, 3400, 1000, 3400, 800];

function row(c1, c2, c3, c4, c5) { return new TableRow({ children: [c1, c2, c3, c4, c5] }); }
function arrowRow() { return row(blank(W[0]), arrow(W[1]), blank(W[2]), arrow(W[3]), blank(W[4])); }

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
  row(blank(W[0]), box("CANDIDATE\nIDENTIFIER SET", W[1], "E0E0E0", true), blank(W[2]),
      box("NATURAL LANGUAGE\nDESCRIPTIONS", W[3], "E0E0E0", true), blank(W[4])),
  arrowRow(),

  // Panel
  new TableRow({ children: [
    blank(W[0]),
    spanBox("CROSS-VENDOR LANGUAGE MODEL PANEL",
            "\u2265 3 models  |  \u2265 2 vendor lineages  |  models are instruments, not targets",
            "F5F5F5", true),
    blank(W[4])
  ]}),
  arrowRow(),

  // Mode 1 + Mode 3
  row(blank(W[0]),
      box("MODE 1\nRecognition WITH\ncontextual frame", W[1], "C5DCF0", true),
      arrow(W[2], ""),
      box("MODE 3\nGeneration\n(compose freely)", W[3], "C5F0C5", true),
      blank(W[4])),
  arrowRow(),

  // Mode 2 + Gen Classification
  row(blank(W[0]),
      box("MODE 2\nRecognition WITHOUT\ncontextual frame", W[1], "C5DCF0", true),
      arrow(W[2], ""),
      box("5-Category\nGeneration\nClassification", W[3], "C5F0C5", false),
      blank(W[4])),
  arrowRow(),

  // Classifications
  row(blank(W[0]),
      box("4-Category\nDual-Mode Delta\nClassification", W[1], "C5DCF0", false),
      arrow(W[2], ""),
      box("Graduated\nGeneration\nAccess Paths", W[3], "C5F0C5", false),
      blank(W[4])),
  arrowRow(),

  // Reduction + Discovery
  row(blank(W[0]),
      box("ITERATIVE REDUCTION\n(minimum surface form)", W[1], "F0E0C5", true),
      arrow(W[2], "\u2190\u2192"),
      box("DISCOVERY OUTPUTS\n(gaps, ambiguities,\npanel-preferred forms)", W[3], "F0E0C5", true),
      blank(W[4])),
  arrowRow(),

  // Output
  new TableRow({ children: [
    blank(W[0]),
    spanBox("BIDIRECTIONAL VOCABULARY",
            "Recognition paths (Modes 1+2) + Generation paths (Mode 3) + Reduction",
            "D0D0D0", true),
    blank(W[4])
  ]}),

  // Spacer
  new TableRow({ children: W.map(w => blank(w)) }),

  // Legend
  new TableRow({ children: [
    blank(W[0]),
    new TableCell({ borders: noBorders, columnSpan: 3, width: { size: W[1]+W[2]+W[3], type: WidthType.DXA },
      children: [
        new Paragraph({ spacing: { before: 200 }, children: [
          new TextRun({ text: "Blue", color: "4472C4", bold: true, size: 16, font: F }),
          new TextRun({ text: " = Recognition measurement (Claims 1-5)    ", size: 16, font: F }),
          new TextRun({ text: "Green", color: "548235", bold: true, size: 16, font: F }),
          new TextRun({ text: " = Generation measurement (Claims 6-10)    ", size: 16, font: F }),
          new TextRun({ text: "Orange", color: "BF8F00", bold: true, size: 16, font: F }),
          new TextRun({ text: " = Shared operations (Claims 4, 8)", size: 16, font: F }),
        ]}),
      ]
    }),
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
  console.log("Drawing sheet: " + buf.length + " bytes");
});

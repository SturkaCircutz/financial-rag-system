package com.financialrag.backend.report;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

@Service
public class ReportExportService {

    private final ObjectMapper objectMapper;

    public ReportExportService(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public ReportExport export(ReportResponse report, ReportExportFormat format) {
        byte[] content = switch (format) {
            case JSON -> json(report);
            case MARKDOWN -> markdown(report).getBytes(StandardCharsets.UTF_8);
            case PDF -> pdf(report);
        };
        return new ReportExport(
                format,
                report.reportId() + "." + format.extension(),
                content);
    }

    private byte[] json(ReportResponse report) {
        try {
            return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsBytes(report);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Could not export report as JSON.", exception);
        }
    }

    private static String markdown(ReportResponse report) {
        StringBuilder markdown = new StringBuilder();
        markdown.append("# Financial RAG Report ").append(report.reportId()).append("\n\n");
        markdown.append("- Status: ").append(report.status()).append("\n");
        markdown.append("- Tickers: ").append(String.join(", ", report.tickers())).append("\n");
        markdown.append("- Report Type: ").append(report.reportType()).append("\n");
        markdown.append("- Created At: ").append(report.createdAt()).append("\n\n");
        markdown.append("## Question\n\n").append(report.question()).append("\n\n");
        markdown.append("## Summary\n\n").append(report.summary()).append("\n\n");
        markdown.append("## Key Findings\n\n");
        for (String finding : report.keyFindings()) {
            markdown.append("- ").append(finding).append("\n");
        }
        markdown.append("\n## Citations\n\n");
        for (Citation citation : report.citations()) {
            markdown.append("- `").append(citation.evidenceId()).append("` ")
                    .append(citation.title())
                    .append(" (").append(citation.sourceType()).append(", ")
                    .append(citation.section()).append(") ")
                    .append(citation.url())
                    .append("\n");
        }
        return markdown.toString();
    }

    private static byte[] pdf(ReportResponse report) {
        List<String> lines = new ArrayList<>();
        lines.add("Financial RAG Report " + report.reportId());
        lines.add("Status: " + report.status());
        lines.add("Tickers: " + String.join(", ", report.tickers()));
        lines.add("Report Type: " + report.reportType());
        lines.add("Created At: " + report.createdAt());
        lines.add("Question: " + report.question());
        lines.add("Summary: " + report.summary());
        lines.add("Key Findings:");
        report.keyFindings().forEach(finding -> lines.add("- " + finding));
        lines.add("Citations:");
        report.citations().forEach(citation -> lines.add("- " + citation.evidenceId() + " " + citation.title()));
        return simplePdf(lines);
    }

    private static byte[] simplePdf(List<String> lines) {
        String content = pdfTextStream(lines);
        byte[] streamBytes = content.getBytes(StandardCharsets.US_ASCII);
        List<byte[]> objects = List.of(
                "<< /Type /Catalog /Pages 2 0 R >>".getBytes(StandardCharsets.US_ASCII),
                "<< /Type /Pages /Kids [3 0 R] /Count 1 >>".getBytes(StandardCharsets.US_ASCII),
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>".getBytes(StandardCharsets.US_ASCII),
                ("<< /Length " + streamBytes.length + " >>\nstream\n" + content + "endstream").getBytes(StandardCharsets.US_ASCII),
                "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>".getBytes(StandardCharsets.US_ASCII));

        ByteArrayOutputStream output = new ByteArrayOutputStream();
        List<Integer> offsets = new ArrayList<>();
        writeAscii(output, "%PDF-1.4\n");
        for (int index = 0; index < objects.size(); index++) {
            offsets.add(output.size());
            writeAscii(output, (index + 1) + " 0 obj\n");
            output.writeBytes(objects.get(index));
            writeAscii(output, "\nendobj\n");
        }
        int xrefOffset = output.size();
        writeAscii(output, "xref\n0 " + (objects.size() + 1) + "\n");
        writeAscii(output, "0000000000 65535 f \n");
        for (Integer offset : offsets) {
            writeAscii(output, String.format("%010d 00000 n \n", offset));
        }
        writeAscii(output, "trailer\n<< /Size " + (objects.size() + 1) + " /Root 1 0 R >>\n");
        writeAscii(output, "startxref\n" + xrefOffset + "\n%%EOF\n");
        return output.toByteArray();
    }

    private static String pdfTextStream(List<String> lines) {
        StringBuilder builder = new StringBuilder("BT\n/F1 11 Tf\n50 750 Td\n14 TL\n");
        for (String line : lines.stream().limit(45).toList()) {
            builder.append("(").append(pdfEscape(line)).append(") Tj\nT*\n");
        }
        builder.append("ET\n");
        return builder.toString();
    }

    private static String pdfEscape(String value) {
        return value.replace("\\", "\\\\")
                .replace("(", "\\(")
                .replace(")", "\\)")
                .replaceAll("[^\\x20-\\x7E]", " ");
    }

    private static void writeAscii(ByteArrayOutputStream output, String value) {
        output.writeBytes(value.getBytes(StandardCharsets.US_ASCII));
    }
}

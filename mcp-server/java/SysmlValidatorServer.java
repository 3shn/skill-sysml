import org.omg.sysml.interactive.SysMLInteractive;
import org.omg.sysml.interactive.SysMLInteractiveResult;
import org.eclipse.xtext.validation.Issue;

import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * Warm, long-lived SysML v2 validator. Loads the standard library once, then serves
 * validation requests over stdin/stdout so the expensive JVM + library load is paid only once.
 *
 * Protocol (one request per line on stdin, one JSON response per line on stdout):
 *   request : <target_path>[\t<context_path> ...]
 *   response: {"ok":bool,"diagnostics":[{"line","column","severity","code","syntax","message"}, ...]}
 *
 * The target file is validated against the standard library. Any context paths are appended
 * AFTER the target content so cross-file references resolve, while the target keeps its own
 * line numbers; only diagnostics within the target's line range are reported.
 *
 * Library directory comes from $SYSML_LIBRARY_PATH. A "READY" line is printed to stdout once
 * the library is loaded. Library-load chatter (System.out "Reading ...") is redirected to stderr
 * so the stdout channel carries only the READY sentinel and JSON responses.
 */
public class SysmlValidatorServer {

    public static void main(String[] args) throws Exception {
        PrintStream realOut = System.out;
        // Silence library-load chatter on the protocol channel.
        System.setOut(System.err);

        String libPath = System.getenv("SYSML_LIBRARY_PATH");
        SysMLInteractive sysml = SysMLInteractive.getInstance();
        if (libPath != null && !libPath.isEmpty()) {
            sysml.loadLibrary(libPath);
        }

        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, "UTF-8"));
        realOut.println("READY");
        realOut.flush();

        String line;
        while ((line = in.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty()) continue;
            if (line.equals("__QUIT__")) break;
            try {
                realOut.println(handle(sysml, line));
            } catch (Exception e) {
                realOut.println("{\"ok\":false,\"diagnostics\":[{\"line\":0,\"column\":0,"
                    + "\"severity\":\"ERROR\",\"code\":\"server-error\",\"syntax\":false,"
                    + "\"message\":\"" + esc(String.valueOf(e.getMessage())) + "\"}]}");
            }
            realOut.flush();
        }
    }

    private static String handle(SysMLInteractive sysml, String line) throws IOException {
        String[] paths = line.split("\t");
        String target = new String(Files.readAllBytes(Paths.get(paths[0])), "UTF-8");
        int targetLines = countLines(target);

        StringBuilder combined = new StringBuilder(target);
        for (int i = 1; i < paths.length; i++) {
            if (paths[i].isEmpty()) continue;
            combined.append("\n// ---8<--- context: ").append(paths[i]).append("\n");
            combined.append(new String(Files.readAllBytes(Paths.get(paths[i])), "UTF-8"));
        }

        SysMLInteractiveResult result = sysml.process(combined.toString(), false);

        StringBuilder sb = new StringBuilder();
        List<DiagJson> diags = new ArrayList<>();
        if (result.getException() != null) {
            diags.add(new DiagJson(0, 0, "ERROR", "exception", false,
                String.valueOf(result.getException().getMessage())));
        } else {
            for (Issue is : result.getIssues()) {
                Integer ln = is.getLineNumber();
                // Only report diagnostics that fall within the target file (context appended after).
                if (paths.length > 1 && ln != null && ln > targetLines) continue;
                diags.add(new DiagJson(
                    ln == null ? 0 : ln,
                    is.getColumn() == null ? 0 : is.getColumn(),
                    String.valueOf(is.getSeverity()),
                    is.getCode(),
                    is.isSyntaxError(),
                    is.getMessage()));
            }
        }
        boolean ok = true;
        for (DiagJson d : diags) if ("ERROR".equals(d.severity)) ok = false;

        sb.append("{\"ok\":").append(ok).append(",\"diagnostics\":[");
        for (int i = 0; i < diags.size(); i++) {
            if (i > 0) sb.append(",");
            sb.append(diags.get(i).toJson());
        }
        sb.append("]}");
        return sb.toString();
    }

    private static int countLines(String s) {
        int n = 1;
        for (int i = 0; i < s.length(); i++) if (s.charAt(i) == '\n') n++;
        return n;
    }

    private static final class DiagJson {
        final int line, column; final String severity, code; final boolean syntax; final String message;
        DiagJson(int line, int column, String severity, String code, boolean syntax, String message) {
            this.line = line; this.column = column; this.severity = severity;
            this.code = code; this.syntax = syntax; this.message = message;
        }
        String toJson() {
            return "{\"line\":" + line + ",\"column\":" + column
                + ",\"severity\":\"" + esc(severity) + "\""
                + ",\"code\":" + (code == null ? "null" : ("\"" + esc(code) + "\""))
                + ",\"syntax\":" + syntax
                + ",\"message\":\"" + esc(message) + "\"}";
        }
    }

    static String esc(String s) {
        if (s == null) return "";
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:
                    if (c < 0x20) b.append(String.format("\\u%04x", (int) c));
                    else b.append(c);
            }
        }
        return b.toString();
    }
}

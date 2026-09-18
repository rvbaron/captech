using Microsoft.Data.Sqlite;

namespace LegacyLift.PlatformApi.Data;

public sealed record ListQuery(
    string? Search,
    string[]? Priority,
    string[]? Category,
    string[]? RuleClass,
    string[]? Pattern,
    string[]? Subject,
    string? Severity,
    bool? HasSmeQuestion,
    bool? HasSuspectedDefect,
    bool? HasCandidate,
    bool? Edited,
    string Sort,
    int Page,
    int PageSize);

public sealed class Requirements(Store store)
{
    private const string RowSelect = """
        SELECT gr.gr_id, gr.name, gr.subject, gr.statement, gr.priority, gr.category,
               gr.rule_class, gr.pattern, gr.modality, gr.confidence_extraction,
               gr.confidence_intent, gr.state, gr.structured_body_type,
               gr.sme_question IS NOT NULL, gr.suspected_defect IS NOT NULL,
               gr.statement <> gr.statement_extracted,
               -- Only an *evaluated* ERROR blocks approval: the gate in the store's
               -- `set_state` is `severity = 'ERROR' AND evaluated = 1`. A row with
               -- evaluated = 0 is a check that could not run, which is review
               -- progress rather than a violation, so it is counted separately.
               (SELECT count(*) FROM gr_finding f
                 WHERE f.gr_id = gr.gr_id AND f.severity='ERROR' AND f.evaluated=1) AS errors,
               (SELECT count(*) FROM gr_finding f
                 WHERE f.gr_id = gr.gr_id AND f.severity='WARN' AND f.evaluated=1),
               (SELECT count(*) FROM gr_finding f
                 WHERE f.gr_id = gr.gr_id AND f.evaluated=0),
               (SELECT count(*) FROM gr_citation c WHERE c.gr_id = gr.gr_id),
               (SELECT count(*) FROM gr_merge_candidate m
                 WHERE m.resolution='unresolved'
                   AND (m.gr_id_existing = gr.gr_id OR m.gr_id_incoming = gr.gr_id))
        FROM gr
        """;

    private static readonly Dictionary<string, string> SortOrders = new(StringComparer.OrdinalIgnoreCase)
    {
        // The ExecPlan's work-ordering signals, exposed as explicit sorts rather
        // than one opinionated default: P0 first, weakest extraction first, and
        // most-blocking first are three different reviewer questions.
        ["priority"] = "CASE gr.priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END, errors DESC, gr.name",
        ["errors"] = "errors DESC, CASE gr.priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END, gr.name",
        ["confidence"] = "CASE gr.confidence_extraction WHEN 'Low' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, gr.name",
        ["name"] = "gr.name",
        ["subject"] = "gr.subject, gr.name",
        ["id"] = "gr.gr_id",
    };

    public (List<Dictionary<string, object?>> Rows, int Total, Dictionary<string, int> Facets) List(ListQuery q)
    {
        using var conn = store.Open();
        var where = new List<string>();
        var ps = new List<(string, object?)>();

        if (!string.IsNullOrWhiteSpace(q.Search))
        {
            where.Add("gr.gr_id IN (SELECT gr_id FROM gr_fts WHERE gr_fts MATCH $q)");
            ps.Add(("$q", FtsQuery(q.Search)));
        }
        AddIn(where, ps, "gr.priority", q.Priority, "pri");
        AddIn(where, ps, "gr.category", q.Category, "cat");
        AddIn(where, ps, "gr.rule_class", q.RuleClass, "rc");
        AddIn(where, ps, "gr.pattern", q.Pattern, "pat");
        AddIn(where, ps, "gr.subject", q.Subject, "sub");

        if (q.Severity is "ERROR" or "WARN")
        {
            where.Add("""
                EXISTS (SELECT 1 FROM gr_finding f
                         WHERE f.gr_id = gr.gr_id AND f.severity = $sev AND f.evaluated = 1)
                """);
            ps.Add(("$sev", q.Severity));
        }
        if (q.HasSmeQuestion == true) where.Add("gr.sme_question IS NOT NULL");
        if (q.HasSuspectedDefect == true) where.Add("gr.suspected_defect IS NOT NULL");
        if (q.Edited == true) where.Add("gr.statement <> gr.statement_extracted");
        if (q.HasCandidate == true)
        {
            where.Add("""
                EXISTS (SELECT 1 FROM gr_merge_candidate m
                         WHERE m.resolution='unresolved'
                           AND (m.gr_id_existing = gr.gr_id OR m.gr_id_incoming = gr.gr_id))
                """);
        }

        var clause = where.Count > 0 ? " WHERE " + string.Join(" AND ", where) : "";

        int total;
        using (var cmd = conn.Cmd($"SELECT count(*) FROM gr{clause}"))
        {
            foreach (var (n, v) in ps) cmd.With(n, v);
            total = Convert.ToInt32(cmd.ExecuteScalar());
        }

        var order = SortOrders.TryGetValue(q.Sort, out var o) ? o : SortOrders["priority"];
        // Two sort orders reference the ERROR count, so the subquery is aliased
        // `errors` in the row select and ORDER BY names the alias.
        var rows = new List<Dictionary<string, object?>>();
        using (var cmd = conn.Cmd($"""
            {RowSelect}{clause}
            ORDER BY {order}
            LIMIT $take OFFSET $skip
            """))
        {
            foreach (var (n, v) in ps) cmd.With(n, v);
            cmd.With("$take", q.PageSize).With("$skip", Math.Max(0, (q.Page - 1) * q.PageSize));
            using var r = cmd.ExecuteReader();
            while (r.Read()) rows.Add(ReadRow(r));
        }

        return (rows, total, Facets(conn));
    }

    private static Dictionary<string, object?> ReadRow(SqliteDataReader r) => new()
    {
        ["grId"] = r.Str(0),
        ["name"] = r.Str(1),
        ["subject"] = r.Str(2),
        ["statement"] = r.Str(3),
        ["priority"] = r.Str(4),
        ["category"] = r.Str(5),
        ["ruleClass"] = r.Str(6),
        ["pattern"] = r.Str(7),
        ["modality"] = r.Str(8),
        ["confidenceExtraction"] = r.Str(9),
        ["confidenceIntent"] = r.Str(10),
        ["state"] = r.Str(11),
        ["structuredBodyType"] = r.Str(12),
        ["hasSmeQuestion"] = r.GetInt32(13) == 1,
        ["hasSuspectedDefect"] = r.GetInt32(14) == 1,
        ["edited"] = r.GetInt32(15) == 1,
        ["errorCount"] = r.GetInt32(16),
        ["warnCount"] = r.GetInt32(17),
        ["notEvaluatedCount"] = r.GetInt32(18),
        ["citationCount"] = r.GetInt32(19),
        ["candidateCount"] = r.GetInt32(20),
    };

    /// <summary>Distinct values for the filter chips, counted over the whole corpus.</summary>
    private static Dictionary<string, int> Facets(SqliteConnection conn)
    {
        var facets = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (var col in new[] { "priority", "category", "rule_class", "pattern", "subject", "modality", "confidence_extraction" })
        {
            using var cmd = conn.Cmd($"SELECT {col}, count(*) FROM gr WHERE {col} IS NOT NULL GROUP BY 1");
            using var r = cmd.ExecuteReader();
            while (r.Read()) facets[$"{col}:{r.GetString(0)}"] = r.GetInt32(1);
        }
        return facets;
    }

    public Dictionary<string, object?>? Detail(string grId)
    {
        using var conn = store.Open();
        Dictionary<string, object?>? gr = null;

        using (var cmd = conn.Cmd("SELECT * FROM gr WHERE gr_id = $id").With("$id", grId))
        using (var r = cmd.ExecuteReader())
        {
            if (r.Read())
            {
                gr = new Dictionary<string, object?>(StringComparer.Ordinal);
                for (var i = 0; i < r.FieldCount; i++)
                    gr[Camel(r.GetName(i))] = r.IsDBNull(i) ? null : r.GetValue(i);
            }
        }
        if (gr is null) return null;

        gr["edited"] = (gr["statement"] as string) != (gr["statementExtracted"] as string);
        gr["citations"] = Citations(conn, grId);
        // The list view's counts come from SQL; `SELECT *` does not carry them,
        // so the detail view derives the same three numbers from the findings.
        var findings = Findings(conn, grId);
        gr["findings"] = findings;
        gr["errorCount"] = CountFindings(findings, "ERROR", evaluated: true);
        gr["warnCount"] = CountFindings(findings, "WARN", evaluated: true);
        gr["notEvaluatedCount"] = findings
            .Cast<Dictionary<string, object?>>()
            .Count(f => f["evaluated"] is false);
        gr["scenarios"] = Scenarios(conn, grId);
        gr["edgeCases"] = EdgeCases(conn, grId);
        gr["candidates"] = CandidatesFor(conn, grId);
        gr["runs"] = RunHits(conn, grId);
        return gr;
    }

    private static int CountFindings(List<object> findings, string severity, bool evaluated) =>
        findings
            .Cast<Dictionary<string, object?>>()
            .Count(f => (string?)f["severity"] == severity
                        && f["evaluated"] is bool e
                        && e == evaluated);

    private static List<object> Citations(SqliteConnection conn, string grId)
    {
        var list = new List<object>();
        using var cmd = conn.Cmd("""
            SELECT citation_id, relative_path, start_line, end_line, anchor_resolution,
                   content_hash, verified_at, provenance, anchor_key
            FROM gr_citation WHERE gr_id = $id
            ORDER BY relative_path, start_line
            """).With("$id", grId);
        using var r = cmd.ExecuteReader();
        while (r.Read())
        {
            list.Add(new Dictionary<string, object?>
            {
                ["citationId"] = r.GetInt64(0),
                ["relativePath"] = r.Str(1),
                ["startLine"] = r.Int(2),
                ["endLine"] = r.Int(3),
                ["anchorResolution"] = r.Str(4),
                ["contentHash"] = r.Str(5),
                ["verifiedAt"] = r.Str(6),
                ["provenance"] = r.Str(7),
                ["anchorKey"] = r.Str(8),
            });
        }
        return list;
    }

    private static List<object> Findings(SqliteConnection conn, string grId)
    {
        var list = new List<object>();
        using var cmd = conn.Cmd("""
            SELECT finding_id, severity, span, message, evaluated
            FROM gr_finding WHERE gr_id = $id
            ORDER BY CASE severity WHEN 'ERROR' THEN 0 ELSE 1 END, finding_id
            """).With("$id", grId);
        using var r = cmd.ExecuteReader();
        while (r.Read())
        {
            var span = r.Str(2);
            var (from, to) = ParseSpan(span);
            list.Add(new Dictionary<string, object?>
            {
                ["findingId"] = r.Str(0),
                ["severity"] = r.Str(1),
                ["span"] = span,
                ["spanStart"] = from,
                ["spanEnd"] = to,
                ["message"] = r.Str(3),
                ["evaluated"] = r.Int(4) == 1,
            });
        }
        return list;
    }

    /// <summary>
    /// A finding's <c>span</c> is a character range within <c>statement</c>, written
    /// "start-end". Some checks are statement-wide and carry a non-range marker;
    /// those return nulls so the client renders them as a banner, not a highlight.
    /// </summary>
    private static (int?, int?) ParseSpan(string? span)
    {
        if (string.IsNullOrWhiteSpace(span)) return (null, null);
        var parts = span.Split('-', 2);
        if (parts.Length == 2
            && int.TryParse(parts[0], out var a)
            && int.TryParse(parts[1], out var b))
        {
            return (a, b);
        }
        return (null, null);
    }

    private static List<object> Scenarios(SqliteConnection conn, string grId)
    {
        var list = new List<object>();
        using var cmd = conn.Cmd("""
            SELECT ordinal, "given", "when", "then", and_clause, provenance
            FROM gr_scenario WHERE gr_id = $id ORDER BY provenance, ordinal
            """).With("$id", grId);
        using var r = cmd.ExecuteReader();
        while (r.Read())
        {
            list.Add(new Dictionary<string, object?>
            {
                ["ordinal"] = r.Int(0),
                ["given"] = r.Str(1),
                ["when"] = r.Str(2),
                ["then"] = r.Str(3),
                ["and"] = r.Str(4),
                ["provenance"] = r.Str(5),
            });
        }
        return list;
    }

    private static List<object> EdgeCases(SqliteConnection conn, string grId)
    {
        var list = new List<object>();
        using var cmd = conn.Cmd("""
            SELECT ordinal, text, provenance FROM gr_edge_case
            WHERE gr_id = $id ORDER BY provenance, ordinal
            """).With("$id", grId);
        using var r = cmd.ExecuteReader();
        while (r.Read())
        {
            list.Add(new Dictionary<string, object?>
            {
                ["ordinal"] = r.Int(0),
                ["text"] = r.Str(1),
                ["provenance"] = r.Str(2),
            });
        }
        return list;
    }

    private static List<object> RunHits(SqliteConnection conn, string grId)
    {
        var list = new List<object>();
        using var cmd = conn.Cmd("""
            SELECT run_id FROM gr_run_hit WHERE gr_id = $id ORDER BY run_id
            """).With("$id", grId);
        using var r = cmd.ExecuteReader();
        while (r.Read()) list.Add(r.GetString(0));
        return list;
    }

    /// <summary>
    /// Merge candidates seen from one requirement's point of view. The pair is
    /// symmetric in the store, so both sides are queried and the *other* record
    /// is what the reviewer needs named.
    /// </summary>
    private static List<object> CandidatesFor(SqliteConnection conn, string grId)
    {
        var list = new List<object>();
        using var cmd = conn.Cmd("""
            SELECT CASE WHEN m.gr_id_existing = $id THEN m.gr_id_incoming ELSE m.gr_id_existing END AS other,
                   CASE WHEN m.gr_id_existing = $id THEN 'existing' ELSE 'incoming' END AS side,
                   m.reason, m.resolution, m.similarity, m.run_id, m.resolved_at,
                   o.name, o.statement, o.priority, o.subject
            FROM gr_merge_candidate m
            JOIN gr o ON o.gr_id = CASE WHEN m.gr_id_existing = $id
                                        THEN m.gr_id_incoming ELSE m.gr_id_existing END
            WHERE m.gr_id_existing = $id OR m.gr_id_incoming = $id
            ORDER BY m.resolution, m.reason, m.similarity DESC
            """).With("$id", grId);
        using var r = cmd.ExecuteReader();
        while (r.Read())
        {
            list.Add(new Dictionary<string, object?>
            {
                ["otherGrId"] = r.Str(0),
                ["thisSide"] = r.Str(1),
                ["reason"] = r.Str(2),
                ["resolution"] = r.Str(3),
                ["similarity"] = r.Dbl(4),
                ["runId"] = r.Str(5),
                ["resolvedAt"] = r.Str(6),
                ["otherName"] = r.Str(7),
                ["otherStatement"] = r.Str(8),
                ["otherPriority"] = r.Str(9),
                ["otherSubject"] = r.Str(10),
            });
        }
        return list;
    }

    /// <summary>The unresolved-candidate queue, as pairs rather than per-record.</summary>
    public List<object> CandidateQueue(string? reason, string resolution = "unresolved")
    {
        using var conn = store.Open();
        var list = new List<object>();
        var filter = reason is null ? "" : " AND m.reason = $reason";
        using var cmd = conn.Cmd($"""
            SELECT m.gr_id_existing, m.gr_id_incoming, m.reason, m.resolution,
                   m.similarity, m.run_id,
                   a.name, a.statement, a.priority, a.subject,
                   b.name, b.statement, b.priority, b.subject
            FROM gr_merge_candidate m
            JOIN gr a ON a.gr_id = m.gr_id_existing
            JOIN gr b ON b.gr_id = m.gr_id_incoming
            WHERE m.resolution = $res{filter}
            ORDER BY m.reason, m.similarity DESC NULLS LAST, a.name
            """).With("$res", resolution);
        if (reason is not null) cmd.With("$reason", reason);
        using var r = cmd.ExecuteReader();
        while (r.Read())
        {
            list.Add(new Dictionary<string, object?>
            {
                ["reason"] = r.Str(2),
                ["resolution"] = r.Str(3),
                ["similarity"] = r.Dbl(4),
                ["runId"] = r.Str(5),
                ["existing"] = new Dictionary<string, object?>
                {
                    ["grId"] = r.Str(0), ["name"] = r.Str(6), ["statement"] = r.Str(7),
                    ["priority"] = r.Str(8), ["subject"] = r.Str(9),
                },
                ["incoming"] = new Dictionary<string, object?>
                {
                    ["grId"] = r.Str(1), ["name"] = r.Str(10), ["statement"] = r.Str(11),
                    ["priority"] = r.Str(12), ["subject"] = r.Str(13),
                },
            });
        }
        return list;
    }

    public Dictionary<string, object?> Stats()
    {
        using var conn = store.Open();
        var stats = new Dictionary<string, object?>(StringComparer.Ordinal);

        stats["total"] = Scalar(conn, "SELECT count(*) FROM gr");
        stats["byState"] = GroupCount(conn, "state");
        stats["byPriority"] = GroupCount(conn, "priority");
        stats["byCategory"] = GroupCount(conn, "category");
        stats["byRuleClass"] = GroupCount(conn, "rule_class");
        stats["byPattern"] = GroupCount(conn, "pattern");
        stats["bySubject"] = GroupCount(conn, "subject");
        stats["byConfidenceExtraction"] = GroupCount(conn, "confidence_extraction");
        stats["byStructuredBodyType"] = GroupCount(conn, "structured_body_type");

        // The store plan's honest measure of review progress: the three
        // extractor-forbidden fields, plus the one definition of a human edit.
        using (var cmd = conn.Cmd("""
            SELECT sum(rationale IS NOT NULL), sum(fit_criterion IS NOT NULL),
                   sum(enforcement_level IS NOT NULL), sum(statement <> statement_extracted),
                   sum(confidence_intent IS NOT NULL), sum(modality_confirmed = 1),
                   sum(reviewed_by IS NOT NULL), sum(owner IS NOT NULL),
                   sum(sme_question IS NOT NULL), sum(suspected_defect IS NOT NULL),
                   sum(as_built IS NOT NULL), sum(structured_body IS NOT NULL)
            FROM gr
            """))
        using (var r = cmd.ExecuteReader())
        {
            r.Read();
            stats["sme"] = new Dictionary<string, object?>
            {
                ["rationale"] = r.Int(0), ["fitCriterion"] = r.Int(1),
                ["enforcementLevel"] = r.Int(2), ["edited"] = r.Int(3),
                ["confidenceIntent"] = r.Int(4), ["modalityConfirmed"] = r.Int(5),
                ["reviewedBy"] = r.Int(6), ["owner"] = r.Int(7),
            };
            stats["extraction"] = new Dictionary<string, object?>
            {
                ["smeQuestion"] = r.Int(8), ["suspectedDefect"] = r.Int(9),
                ["asBuilt"] = r.Int(10), ["structuredBody"] = r.Int(11),
            };
        }

        // The not-evaluated count is its own figure and is never folded into
        // `error`: it measures how much of the corpus has checks nobody could run.
        stats["findings"] = new Dictionary<string, object?>
        {
            ["error"] = Scalar(conn,
                "SELECT count(*) FROM gr_finding WHERE severity='ERROR' AND evaluated=1"),
            ["warn"] = Scalar(conn,
                "SELECT count(*) FROM gr_finding WHERE severity='WARN' AND evaluated=1"),
            ["notEvaluated"] = Scalar(conn, "SELECT count(*) FROM gr_finding WHERE evaluated=0"),
            ["rulesWithError"] = Scalar(conn,
                "SELECT count(DISTINCT gr_id) FROM gr_finding WHERE severity='ERROR' AND evaluated=1"),
            ["rulesNotEvaluated"] = Scalar(conn,
                "SELECT count(DISTINCT gr_id) FROM gr_finding WHERE evaluated=0"),
            ["rulesClean"] = Scalar(conn,
                "SELECT count(*) FROM gr WHERE gr_id NOT IN (SELECT gr_id FROM gr_finding)"),
            ["byId"] = FindingBreakdown(conn),
        };

        stats["citations"] = new Dictionary<string, object?>
        {
            ["total"] = Scalar(conn, "SELECT count(*) FROM gr_citation"),
            ["files"] = Scalar(conn, "SELECT count(DISTINCT relative_path) FROM gr_citation"),
            ["byResolution"] = GroupCount(conn, "anchor_resolution", "gr_citation"),
        };

        stats["candidates"] = new Dictionary<string, object?>
        {
            ["unresolved"] = Scalar(conn,
                "SELECT count(*) FROM gr_merge_candidate WHERE resolution='unresolved'"),
            ["byReason"] = GroupCount(conn, "reason", "gr_merge_candidate"),
        };

        stats["scenarios"] = Scalar(conn, "SELECT count(*) FROM gr_scenario");
        stats["edgeCases"] = Scalar(conn, "SELECT count(*) FROM gr_edge_case");
        stats["runs"] = Runs(conn);
        return stats;
    }

    private static List<object> Runs(SqliteConnection conn)
    {
        var list = new List<object>();
        using var cmd = conn.Cmd("""
            SELECT run_id, system, started_at, finished_at, rounds_run, round_cap,
                   stop_reason, rules_in, rules_new, rules_merged, rules_candidate,
                   rules_rejected, not_accounted_for, final_round_chunk_coverage_pct,
                   coverage_source
            FROM gr_run ORDER BY run_id
            """);
        using var r = cmd.ExecuteReader();
        while (r.Read())
        {
            list.Add(new Dictionary<string, object?>
            {
                ["runId"] = r.Str(0), ["system"] = r.Str(1),
                ["startedAt"] = r.Str(2), ["finishedAt"] = r.Str(3),
                ["roundsRun"] = r.Int(4), ["roundCap"] = r.Int(5),
                ["stopReason"] = r.Str(6), ["rulesIn"] = r.Int(7),
                ["rulesNew"] = r.Int(8), ["rulesMerged"] = r.Int(9),
                ["rulesCandidate"] = r.Int(10), ["rulesRejected"] = r.Int(11),
                ["notAccountedFor"] = r.Int(12),
                ["finalRoundChunkCoveragePct"] = r.Dbl(13),
                ["coverageSource"] = r.Str(14),
            });
        }
        return list;
    }

    private static List<object> FindingBreakdown(SqliteConnection conn)
    {
        var list = new List<object>();
        using var cmd = conn.Cmd("""
            SELECT finding_id, severity, count(*) c, count(DISTINCT gr_id) rules, evaluated
            FROM gr_finding GROUP BY finding_id, severity, evaluated ORDER BY c DESC
            """);
        using var r = cmd.ExecuteReader();
        while (r.Read())
        {
            list.Add(new Dictionary<string, object?>
            {
                ["findingId"] = r.Str(0), ["severity"] = r.Str(1),
                ["count"] = r.Int(2), ["rules"] = r.Int(3),
                ["evaluated"] = r.Int(4) == 1,
            });
        }
        return list;
    }

    private static int Scalar(SqliteConnection conn, string sql)
    {
        using var cmd = conn.Cmd(sql);
        return Convert.ToInt32(cmd.ExecuteScalar());
    }

    private static Dictionary<string, int> GroupCount(SqliteConnection conn, string col, string table = "gr")
    {
        var map = new Dictionary<string, int>(StringComparer.Ordinal);
        using var cmd = conn.Cmd(
            $"SELECT coalesce({col}, '(none)'), count(*) FROM {table} GROUP BY 1 ORDER BY 2 DESC");
        using var r = cmd.ExecuteReader();
        while (r.Read()) map[r.GetString(0)] = r.GetInt32(1);
        return map;
    }

    private static void AddIn(
        List<string> where, List<(string, object?)> ps, string col, string[]? values, string prefix)
    {
        if (values is null || values.Length == 0) return;
        var names = new List<string>();
        for (var i = 0; i < values.Length; i++)
        {
            var n = $"${prefix}{i}";
            names.Add(n);
            ps.Add((n, values[i]));
        }
        where.Add($"{col} IN ({string.Join(", ", names)})");
    }

    /// <summary>
    /// Turn free text into an FTS5 prefix query, quoting each term so that
    /// punctuation a reviewer pastes in (a gr_id, a dotted path) cannot be read
    /// as FTS operator syntax.
    /// </summary>
    private static string FtsQuery(string search)
    {
        var terms = search
            .Split([' ', '\t', ',', ';'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(t => t.Replace("\"", ""))
            .Where(t => t.Length > 0)
            .Select(t => $"\"{t}\"*");
        var joined = string.Join(" AND ", terms);
        return joined.Length == 0 ? "\"\"" : joined;
    }

    private static string Camel(string snake)
    {
        var parts = snake.Split('_');
        return string.Concat(parts.Select((p, i) =>
            i == 0 ? p : char.ToUpperInvariant(p[0]) + p[1..]));
    }
}

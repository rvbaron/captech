using System.Text.Json;
using System.Text.Json.Serialization;
using LegacyLift.PlatformApi.Data;

var builder = WebApplication.CreateBuilder(args);

builder.Services.ConfigureHttpJsonOptions(o =>
{
    o.SerializerOptions.DefaultIgnoreCondition = JsonIgnoreCondition.Never;
    o.SerializerOptions.PropertyNamingPolicy = null;
});

// Milestone 1 is read-only, so CORS is wide open to the dev server only: the
// API is never deployed anywhere, it runs from VS Code beside `ng serve`.
builder.Services.AddCors(o => o.AddDefaultPolicy(p => p
    .WithOrigins("http://localhost:4200", "http://127.0.0.1:4200")
    .AllowAnyHeader()
    .AllowAnyMethod()));

var dataRoot = builder.Configuration["DataRoot"]
               ?? Path.Combine(builder.Environment.ContentRootPath, "..", "data");
dataRoot = Path.GetFullPath(dataRoot);

var app = builder.Build();
app.UseCors();

Catalog? catalog = null;
string? catalogError = null;
try
{
    catalog = new Catalog(dataRoot);
}
catch (Exception ex)
{
    catalogError = ex.Message;
    app.Logger.LogError("{Message}", ex.Message);
}

var requirementsCache = new Dictionary<string, Requirements>(StringComparer.Ordinal);

Requirements? RequirementsFor(string systemId)
{
    if (catalog is null) return null;
    if (requirementsCache.TryGetValue(systemId, out var cached)) return cached;
    var store = catalog.StoreFor(systemId);
    if (store is null || !store.HasTable("gr")) return null;
    var reqs = new Requirements(store);
    requirementsCache[systemId] = reqs;
    return reqs;
}

app.MapGet("/api/health", () => Results.Ok(new
{
    status = catalog is null ? "no-data" : "ok",
    dataRoot,
    error = catalogError,
}));

app.MapGet("/api/projects", () => catalog is null
    ? Results.Problem(catalogError, statusCode: 503)
    : Results.Content(catalog.Projects.ToJsonString(), "application/json"));

app.MapGet("/api/projects/{projectId}", (string projectId) =>
{
    var node = catalog?.Project(projectId);
    return node is null
        ? Results.NotFound(new { error = $"no project '{projectId}'" })
        : Results.Content(node.ToJsonString(), "application/json");
});

app.MapGet("/api/systems/{systemId}", (string systemId) =>
{
    var node = catalog?.System(systemId);
    return node is null
        ? Results.NotFound(new { error = $"no system '{systemId}'" })
        : Results.Content(node.ToJsonString(), "application/json");
});

app.MapGet("/api/systems/{systemId}/stats", (string systemId) =>
{
    var reqs = RequirementsFor(systemId);
    return reqs is null
        ? Results.Ok(new { hasRequirements = false })
        : Results.Ok(reqs.Stats());
});

app.MapGet("/api/systems/{systemId}/requirements", (
    string systemId, HttpRequest req) =>
{
    var reqs = RequirementsFor(systemId);
    if (reqs is null) return Results.Ok(new { total = 0, page = 1, rows = Array.Empty<object>(), hasRequirements = false });

    var q = req.Query;
    string[]? Many(string key) => q[key].Count == 0
        ? null
        : q[key].SelectMany(v => (v ?? "").Split(',', StringSplitOptions.RemoveEmptyEntries)).ToArray();
    bool? Flag(string key) => q[key].Count == 0 ? null : q[key] == "true" || q[key] == "1";

    var page = int.TryParse(q["page"], out var p) && p > 0 ? p : 1;
    var pageSize = int.TryParse(q["pageSize"], out var s) && s is > 0 and <= 500 ? s : 25;

    var query = new ListQuery(
        Search: q["search"],
        Priority: Many("priority"),
        Category: Many("category"),
        RuleClass: Many("ruleClass"),
        Pattern: Many("pattern"),
        Subject: Many("subject"),
        Severity: q["severity"],
        HasSmeQuestion: Flag("smeQuestion"),
        HasSuspectedDefect: Flag("suspectedDefect"),
        HasCandidate: Flag("candidate"),
        Edited: Flag("edited"),
        Sort: q["sort"].ToString() is { Length: > 0 } sort ? sort : "priority",
        Page: page,
        PageSize: pageSize);

    var (rows, total, facets) = reqs.List(query);
    return Results.Ok(new
    {
        hasRequirements = true,
        total,
        page,
        pageSize,
        rows,
        facets,
    });
});

app.MapGet("/api/systems/{systemId}/requirements/{grId}", (string systemId, string grId) =>
{
    var reqs = RequirementsFor(systemId);
    var detail = reqs?.Detail(grId);
    return detail is null
        ? Results.NotFound(new { error = $"no requirement '{grId}'" })
        : Results.Ok(detail);
});

app.MapGet("/api/systems/{systemId}/candidates", (string systemId, string? reason) =>
{
    var reqs = RequirementsFor(systemId);
    return reqs is null
        ? Results.Ok(Array.Empty<object>())
        : Results.Ok(reqs.CandidateQueue(reason));
});

app.MapGet("/api/systems/{systemId}/citations/{citationId:long}/snippet",
    (string systemId, long citationId) =>
{
    var node = catalog?.Snippet(systemId, citationId);
    return node is null
        ? Results.NotFound(new { error = "no snippet for that citation" })
        : Results.Content(node.ToJsonString(), "application/json");
});

// ---- File-backed artifacts -------------------------------------------------
// Every path is resolved under the system's own data directory and then checked
// to still be inside it, so a traversal in the route cannot read elsewhere.

string? SafePath(string systemId, params string[] parts)
{
    if (catalog is null) return null;
    var root = Path.GetFullPath(catalog.SystemDir(systemId));
    var full = Path.GetFullPath(Path.Combine([root, .. parts]));
    return full.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.Ordinal)
           && File.Exists(full)
        ? full
        : null;
}

app.MapGet("/api/systems/{systemId}/docs/{name}", (string systemId, string name) =>
{
    var path = SafePath(systemId, "docs", name);
    return path is null
        ? Results.NotFound(new { error = $"no document '{name}'" })
        : Results.Text(File.ReadAllText(path), "text/markdown");
});

app.MapGet("/api/systems/{systemId}/diagrams/{name}", (string systemId, string name) =>
{
    var path = SafePath(systemId, "diagrams", name);
    return path is null
        ? Results.NotFound(new { error = $"no diagram '{name}'" })
        : Results.Text(File.ReadAllText(path), "text/plain");
});

app.MapGet("/api/systems/{systemId}/topology", (string systemId) =>
{
    var path = SafePath(systemId, "TOPOLOGY.html");
    return path is null
        ? Results.NotFound(new { error = "no topology page" })
        : Results.File(path, "text/html");
});

app.MapGet("/api/systems/{systemId}/domains", (string systemId) =>
{
    var path = SafePath(systemId, "domains.json");
    if (path is null) return Results.NotFound(new { error = "no domains.json" });

    // domains.json is the assess output; file counts per domain come from the
    // store's file_domains mirror, which is the canonical tagging.
    var doc = JsonDocument.Parse(File.ReadAllText(path));
    var counts = new Dictionary<string, int>(StringComparer.Ordinal);
    var store = catalog?.StoreFor(systemId);
    if (store is not null && store.HasTable("file_domains"))
    {
        using var conn = store.Open();
        using var cmd = conn.Cmd("SELECT domain, count(*) FROM file_domains GROUP BY 1 ORDER BY 2 DESC");
        using var r = cmd.ExecuteReader();
        while (r.Read()) counts[r.GetString(0)] = r.GetInt32(1);
    }
    return Results.Ok(new { definition = doc.RootElement, fileCounts = counts });
});

app.Run();

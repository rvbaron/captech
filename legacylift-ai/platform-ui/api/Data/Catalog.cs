using System.Text.Json;
using System.Text.Json.Nodes;

namespace LegacyLift.PlatformApi.Data;

/// <summary>
/// The project/system catalog, read once from <c>data/projects.json</c>. That
/// file is authored by <c>platform-ui/tools/prepare_data.py</c>; for Milestone 1
/// it is the whole of "settings".
/// </summary>
public sealed class Catalog
{
    private readonly Dictionary<string, Store> _stores = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Dictionary<string, JsonNode?>> _snippets = new(StringComparer.Ordinal);

    public string DataRoot { get; }
    public JsonNode Projects { get; }

    public Catalog(string dataRoot)
    {
        DataRoot = dataRoot;
        var manifest = Path.Combine(dataRoot, "projects.json");
        if (!File.Exists(manifest))
        {
            throw new FileNotFoundException(
                $"No demo dataset at {manifest}. Run: python platform-ui/tools/prepare_data.py",
                manifest);
        }

        Projects = JsonNode.Parse(File.ReadAllText(manifest))
                   ?? throw new InvalidDataException("projects.json is empty");

        foreach (var system in EnumerateSystems())
        {
            var id = system["systemId"]?.GetValue<string>();
            if (id is null) continue;
            var db = Path.Combine(dataRoot, id, "knowledge.sqlite");
            if (File.Exists(db)) _stores[id] = new Store(db);
        }
    }

    public IEnumerable<JsonNode> EnumerateSystems() =>
        (Projects["projects"]?.AsArray() ?? [])
        .Where(p => p is not null)
        .SelectMany(p => (p!["systems"]?.AsArray() ?? []).Where(s => s is not null)!)
        .Select(s => s!);

    public JsonNode? Project(string projectId) =>
        (Projects["projects"]?.AsArray() ?? [])
        .FirstOrDefault(p => p?["projectId"]?.GetValue<string>() == projectId);

    public JsonNode? System(string systemId) =>
        EnumerateSystems().FirstOrDefault(s => s["systemId"]?.GetValue<string>() == systemId);

    public Store? StoreFor(string systemId) =>
        _stores.TryGetValue(systemId, out var s) ? s : null;

    public string SystemDir(string systemId) => Path.Combine(DataRoot, systemId);

    /// <summary>Cited source slices, lazily loaded per system.</summary>
    public JsonNode? Snippet(string systemId, long citationId)
    {
        if (!_snippets.TryGetValue(systemId, out var map))
        {
            map = new Dictionary<string, JsonNode?>(StringComparer.Ordinal);
            var path = Path.Combine(SystemDir(systemId), "snippets.json");
            if (File.Exists(path))
            {
                var parsed = JsonNode.Parse(File.ReadAllText(path))?.AsObject();
                if (parsed is not null)
                {
                    foreach (var kv in parsed) map[kv.Key] = kv.Value?.DeepClone();
                }
            }
            _snippets[systemId] = map;
        }
        return map.TryGetValue(citationId.ToString(), out var node) ? node : null;
    }
}

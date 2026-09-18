using Microsoft.Data.Sqlite;

namespace LegacyLift.PlatformApi.Data;

/// <summary>
/// Read-only access to a copied <c>knowledge.sqlite</c>. Every connection is
/// opened <c>Mode=ReadOnly</c>: Milestone 1 of the review UI has no write path,
/// and the store this reads is a copy of a frozen extraction corpus.
/// </summary>
public sealed class Store(string dbPath)
{
    private readonly string _connectionString = new SqliteConnectionStringBuilder
    {
        DataSource = dbPath,
        Mode = SqliteOpenMode.ReadOnly,
        Cache = SqliteCacheMode.Shared,
    }.ToString();

    public SqliteConnection Open()
    {
        var conn = new SqliteConnection(_connectionString);
        conn.Open();
        return conn;
    }

    public bool HasTable(string name)
    {
        using var conn = Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT 1 FROM sqlite_master WHERE type='table' AND name=$n";
        cmd.Parameters.AddWithValue("$n", name);
        return cmd.ExecuteScalar() is not null;
    }
}

public static class SqliteExtensions
{
    public static string? Str(this SqliteDataReader r, int i) =>
        r.IsDBNull(i) ? null : r.GetString(i);

    public static int? Int(this SqliteDataReader r, int i) =>
        r.IsDBNull(i) ? null : r.GetInt32(i);

    public static double? Dbl(this SqliteDataReader r, int i) =>
        r.IsDBNull(i) ? null : r.GetDouble(i);

    public static SqliteCommand Cmd(this SqliteConnection conn, string sql)
    {
        var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        return cmd;
    }

    public static SqliteCommand With(this SqliteCommand cmd, string name, object? value)
    {
        cmd.Parameters.AddWithValue(name, value ?? DBNull.Value);
        return cmd;
    }
}

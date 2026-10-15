import { Pool, type QueryResultRow } from "pg";

let pool: Pool | null = null;

function connection(): Pool {
  if (!pool) {
    const url = process.env.DATABASE_URL;
    if (!url) throw new Error("DATABASE_URL must be set.");
    pool = new Pool({ connectionString: url, max: 5 });
  }
  return pool;
}

export async function query<T extends QueryResultRow>(
  sql: string,
  params: unknown[] = [],
): Promise<T[]> {
  const result = await connection().query<T>(sql, params);
  return result.rows;
}

export async function one<T extends QueryResultRow>(
  sql: string,
  params: unknown[] = [],
): Promise<T | null> {
  const rows = await query<T>(sql, params);
  return rows[0] ?? null;
}

export async function execute(sql: string, params: unknown[] = []): Promise<number> {
  const result = await connection().query(sql, params);
  return result.rowCount ?? 0;
}

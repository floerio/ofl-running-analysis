import sys
import matplotlib.pyplot as plt
import core


def handle(question: str, schema: str):
    print("\n⏳ Generating SQL...")
    sql = core.generate_sql(question, schema)
    print(f"   SQL: {sql}\n")

    print("⏳ Querying data...")
    try:
        df, final_sql, attempts_log = core.run_query_with_retries(sql, schema)
        for line in attempts_log:
            print(f"   ⚠️  {line}")
        if final_sql != sql:
            print(f"   🔧 Fixed SQL: {final_sql}\n")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return

    print("⏳ Formulating answer...")
    answer = core.formulate_answer(question, df)
    print(f"\n💬 Answer:\n{answer}\n")

    chart_code = core.generate_chart_code(question, df)
    if chart_code:
        print("📈 Rendering chart...")
        fig = core.render_chart(chart_code, question, df)
        if fig:
            plt.show()
        else:
            print("   ⚠️  Chart error (see app.log)")

    print("-" * 60)


def main():
    print("📊 AI Data Assistant (type '/exit', 'exit' or 'quit' to quit)\n")
    print(core.ensure_parquet())
    schema = core.get_schema()

    questions = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else []
    if questions:
        handle(questions[0], schema)
        return

    while True:
        question = input("Your question: ").strip()
        if question.lower() in ("exit", "quit", "/exit"):
            break
        if not question:
            continue
        handle(question, schema)


if __name__ == "__main__":
    main()

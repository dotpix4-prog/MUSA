import asyncio
import typer
from rich.console import Console
from rich.markdown import Markdown

from musa.crawler.crawler import Crawler
from musa.search.embeddings import Embedder
from musa.storage.database import Database
from musa.search.hybrid import HybridSearcher
from musa.search.generator import Generator
from musa.config import Config

app = typer.Typer(
    name="musa",
    help="MUSA — an AI-powered search engine.",
    no_args_is_help=True,
)

console = Console()


@app.command()
def ask(query: str) -> None:
    """Ask MUSA a question based on indexed documents."""
    console.print("\n[bold]MUSA AI Answer[/bold]")
    console.print(f"Question: {query}\n")

    try:
        config = Config()
        api_key = config.groq_api_key
    except EnvironmentError as e:
        console.print(f"[red]Error:[/red] {e}")
        return

    database = Database()
    try:
        # 1. Retrieval
        searcher = HybridSearcher(database)
        docs = searcher.search(query, top_n=5)

        if not docs:
            console.print("[dim]No relevant documents found to answer the question.[/dim]")
            return

        # 2. Generation
        generator = Generator(api_key)
        with console.status("[bold green]Thinking..."):
            answer = generator.generate_answer(query, docs)

        # 3. Output
        console.print(Markdown(answer))
        console.print("\n[bold]Sources:[/bold]")

        citations = generator.extract_citations(answer, docs)
        if citations:
            for i, doc in enumerate(citations, 1):
                console.print(f"{i}. [blue]{doc.title}[/blue] - [green]{doc.url}[/green]")
        else:
            console.print("[dim]No specific sources cited.[/dim]")

    except Exception as e:
        console.print(f"[red]An unexpected error occurred:[/red] {e}")
    finally:
        database.close()


@app.command()
def search(
    query: str,
    semantic: bool = typer.Option(
        False, help="Use semantic search instead of keyword search."
    ),
    hybrid: bool = typer.Option(
        False, help="Use hybrid search (combines keyword and semantic)."
    ),
) -> None:
    """Search the MUSA index."""
    console.print("\n[bold]MUSA Search[/bold]")
    console.print(f"Query: {query}\n")

    database = Database()

    try:
        if hybrid:
            searcher = HybridSearcher(database)
            results = searcher.search(query)
        elif semantic:
            embedder = Embedder()
            query_vector = embedder.encode(query)
            results = database.semantic_search(query_vector)
        else:
            results = database.lexical_search(query)
    finally:
        database.close()

    if not results:
        console.print("[dim]No results found.[/dim]")
        return

    for i, doc in enumerate(results, 1):
        console.print(f"{i}. [blue]{doc.title}[/blue]")
        console.print(f"   [green]{doc.url}[/green]")
        if doc.score is not None:
            console.print(f"   Score: {doc.score:.4f}")
        # Print a small snippet of the content
        snippet = doc.content[:150].replace("\n", " ") + "..."
        console.print(f"   {snippet}\n")


@app.command()
def crawl(
    url: str,
    max_pages: int = typer.Option(1, help="Maximum number of pages to crawl."),
) -> None:
    """Crawl and index a webpage."""

    console.print(
        f"\n[bold]Crawling:[/bold] {url} (max {max_pages} pages)\n"
    )

    database = Database()
    crawler = Crawler(database, max_pages=max_pages)

    try:
        asyncio.run(crawler.crawl(url))
    finally:
        database.close()


@app.command()
def stats() -> None:
    """Show MUSA index statistics."""

    database = Database()

    console.print("\n[bold]MUSA Statistics[/bold]")
    console.print(
        f"Documents: {database.count_documents()}"
    )

    database.close()


if __name__ == "__main__":
    app()

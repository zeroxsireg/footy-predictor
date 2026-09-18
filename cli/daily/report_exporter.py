"""
Report Exporter for Daily Analysis.

Handles saving and formatting of daily analysis reports to text/markdown files.
"""

from datetime import datetime


class DailyReportExporter:
    """Exports daily league analysis results to readable text files."""

    @staticmethod
    def offer_save_results(analysis):
        """Offer to save analysis results to file."""
        print("\n💾 SALVATAGGIO RISULTATI")
        print("-" * 30)
        print("💡 Vuoi salvare i risultati dell'analisi in un file?")
        print("📄 Formato: Testo leggibile con tutti i picks e combinazioni")

        while True:
            try:
                save_choice = input("\n💾 Salvare i risultati? (s/n): ").strip().lower()
                if save_choice in ["s", "si", "y", "yes"]:
                    DailyReportExporter.save_results_to_file(analysis)
                    break
                elif save_choice in ["n", "no"]:
                    print("📄 Risultati non salvati")
                    break
                else:
                    print("❌ Risposta non valida. Usa 's' per sì o 'n' per no.")
            except KeyboardInterrupt:
                print("\n📄 Operazione di salvataggio annullata")
                break

    @staticmethod
    def save_results_to_file(analysis):
        """Save analysis results to a text file."""
        try:
            timestamp = analysis.analysis_date.strftime("%Y%m%d_%H%M%S")
            league_safe = analysis.league_name.replace(" ", "_").replace("UEFA_", "")
            filename = f"daily_analysis_{league_safe}_{timestamp}.txt"

            content = DailyReportExporter.generate_file_content(analysis)

            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"✅ Risultati salvati in: {filename}")
        except Exception as e:
            print(f"❌ Errore nel salvataggio: {e}")

    @staticmethod
    def generate_file_content(analysis) -> str:
        """Generate text content for file save."""
        lines = [
            "🏆 FOOTY PREDICTOR - ANALISI GIORNATA COMPLETA",
            "=" * 60,
            f"📅 Campionato: {analysis.league_name}",
            f"📊 Giornata: {analysis.matchday}",
            f"📈 Partite analizzate: {analysis.matches_analyzed}",
            f"🎯 Picks totali: {analysis.total_picks}",
            f"⏰ Data analisi: {analysis.analysis_date.strftime('%d/%m/%Y %H:%M')}",
            "",
            "📈 RIEPILOGO STATISTICHE:",
            f"   🔥 High Confidence: {analysis.summary['high_confidence_picks']}",
            f"   ⚡ Medium Confidence: {analysis.summary['medium_confidence_picks']}",
            f"   📊 Confidenza media: {analysis.summary['average_confidence']:.1f}%",
            "",
            f"🥇 TOP {len(analysis.top_picks)} PICKS:",
            "-" * 40,
        ]

        for i, pick in enumerate(analysis.top_picks, 1):
            confidence_emoji = "🔥" if pick.confidence == "HIGH" else "⚡"
            time_str = pick.match_time.strftime("%H:%M")
            lines.extend([
                f"{i:2d}. {confidence_emoji} {pick.home_team} vs {pick.away_team}",
                f"    ⏰ {time_str} │ {pick.market}: {pick.selection}",
                f"    💰 {pick.odds_range} │ {pick.percentage:.1f}%",
                f"    💬 {pick.reasoning}",
                "",
            ])

        if analysis.combinations:
            lines.extend([
                "🎯 COMBINAZIONI OTTIMALI:",
                "-" * 30,
            ])
            for i, combo in enumerate(analysis.combinations, 1):
                risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(
                    combo.get("risk_level", "MEDIUM"), "⚪"
                )
                lines.extend([
                    f"{i}. {risk_emoji} {combo.get('description', 'Combinazione')}",
                    f"   📊 Confidenza: {combo.get('confidence', 0):.1f}%",
                    f"   💰 Odds stimate: {combo.get('estimated_odds', 0):.1f}",
                    "",
                ])

        return "\n".join(lines)

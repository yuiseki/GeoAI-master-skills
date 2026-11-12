t=open("scripts/report_template.md",encoding="utf-8").read()
for k,f in [("top10_cells","top10_cells_res9.md"),("top10_clusters_res9","top10_clusters_res9.md"),("top10_clusters_res8","top10_clusters_res8.md"),("ward_table","ward_table.md")]:
    t=t.replace("{{"+k+"}}",open("outputs/"+f,encoding="utf-8").read().strip())
open("report.md","w",encoding="utf-8").write(t)

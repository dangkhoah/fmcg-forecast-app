import csv
import io
import openpyxl
import pandas as pd
# from fastapi.responses import StreamingResponse
from fastapi import Response


def export_csv(dates: list[str], values: list[float], lower: list[float] | None, upper: list[float] | None, records: list[dict] | None = None) -> Response:
    output = io.StringIO()
    
    if records:
        df = pd.DataFrame(records)
        df.to_csv(output, index=False)
    else:
        writer = csv.writer(output)
        writer.writerow(["date", "forecast", "lower_bound", "upper_bound"])
        for i in range(len(dates)):
            writer.writerow([dates[i], values[i], lower[i] if lower else "", upper[i] if upper else ""])
    
    return Response(
        content=output.getvalue().encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=forecast.csv"},
    )


def export_excel(dates: list[str], values: list[float], lower: list[float] | None, upper: list[float] | None, records: list[dict] | None = None) -> Response:
    output = io.BytesIO()
    
    if records:
        df = pd.DataFrame(records)
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Forecast')
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Forecast"
        ws.append(["date", "forecast", "lower_bound", "upper_bound"])
        for i in range(len(dates)):
            ws.append([dates[i], values[i], lower[i] if lower else "", upper[i] if upper else ""])
        wb.save(output)

    # output.seek(0)
    # return StreamingResponse(
    #     iter([output.getvalue()]),
    #     media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    #     headers={"Content-Disposition": "attachment; filename=forecast.xlsx"},
    # )

    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=forecast.xlsx"},
    )

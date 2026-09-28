"use client";

import React, { useRef } from "react";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  ColumnDef,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";

interface VirtualDataTableProps<TData> {
  data: TData[];
  columns: ColumnDef<TData, any>[];
  totalSummaryRow?: React.ReactNode;
  height?: string;
}

export function VirtualDataTable<TData>({
  data,
  columns,
  totalSummaryRow,
  height = "560px",
}: VirtualDataTableProps<TData>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const tableContainerRef = useRef<HTMLDivElement>(null);
  const rows = table.getRowModel().rows;

  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => tableContainerRef.current,
    estimateSize: () => 40,
    overscan: 10,
  });

  return (
    <div className="border border-slate-200 rounded-2xl bg-white overflow-hidden shadow-xs flex flex-col">
      <div
        ref={tableContainerRef}
        style={{ height, overflow: "auto" }}
        className="relative"
      >
        <table className="w-full text-left border-collapse text-xs">
          {/* Sticky Header */}
          <thead className="bg-slate-900 text-white sticky top-0 z-20 shadow-xs">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    colSpan={header.colSpan}
                    className="p-3 font-semibold text-slate-200 border-b border-slate-800 tracking-wide uppercase text-[11px]"
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>

          {/* Virtualized Body */}
          <tbody
            style={{
              height: `${rowVirtualizer.getTotalSize()}px`,
              position: "relative",
            }}
          >
            {rowVirtualizer.getVirtualItems().map((virtualRow) => {
              const row = rows[virtualRow.index];
              return (
                <tr
                  key={row.id}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    height: `${virtualRow.size}px`,
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                  className={`flex items-center border-b border-slate-100 hover:bg-blue-50/50 transition-colors ${
                    virtualRow.index % 2 === 0 ? "bg-white" : "bg-slate-50/40"
                  }`}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="p-3 text-slate-700 whitespace-nowrap overflow-hidden text-ellipsis flex-1"
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>

        {data.length === 0 && (
          <div className="p-12 text-center text-slate-400 text-xs">
            Ushbu davr bo'yicha hech qanday ma'lumot topilmadi.
          </div>
        )}
      </div>

      {/* Floating Summary Bar at bottom */}
      {totalSummaryRow && (
        <div className="bg-slate-100 border-t-2 border-slate-300 p-3 font-bold text-slate-800 text-xs shadow-inner">
          {totalSummaryRow}
        </div>
      )}
    </div>
  );
}

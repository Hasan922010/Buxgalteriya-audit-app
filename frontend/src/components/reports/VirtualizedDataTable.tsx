"use client";

import React, { useRef, useState, useMemo } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { FileSpreadsheet, FileDown, Search, ArrowUpDown } from "lucide-react";

export interface ColumnDef<T> {
  header: string;
  accessorKey: keyof T | string;
  cell?: (row: T) => React.ReactNode;
  align?: "left" | "center" | "right";
  width?: string | number;
}

interface VirtualizedDataTableProps<T> {
  title: string;
  subtitle?: string;
  columns: ColumnDef<T>[];
  data: T[];
  onExportExcel?: () => void;
  onExportPdf?: () => void;
  totalsRow?: React.ReactNode;
}

export function VirtualizedDataTable<T extends Record<string, any>>({
  title,
  subtitle,
  columns,
  data,
  onExportExcel,
  onExportPdf,
  totalsRow,
}: VirtualizedDataTableProps<T>) {
  const [searchQuery, setSearchQuery] = useState<string>("");
  const parentRef = useRef<HTMLDivElement>(null);

  // Filter rows based on search
  const filteredData = useMemo(() => {
    if (!searchQuery.trim()) return data;
    const q = searchQuery.toLowerCase();
    return data.filter((row) =>
      Object.values(row).some((val) =>
        val !== null && val !== undefined && String(val).toLowerCase().includes(q)
      )
    );
  }, [data, searchQuery]);

  // Virtualizer for smooth 50,000+ row rendering
  const rowVirtualizer = useVirtualizer({
    count: filteredData.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 40,
    overscan: 20,
  });

  return (
    <div className="flex flex-col h-full bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
      {/* Top Header & Export Action Toolbar */}
      <div className="p-4 bg-slate-900/90 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-white tracking-wide">{title}</h2>
          {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
        </div>

        <div className="flex items-center gap-3">
          {/* Search Box */}
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Qidiruv (nomi, kodi, raqam)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-700/80 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500 w-60"
            />
          </div>

          {/* Export Buttons */}
          {onExportExcel && (
            <button
              onClick={onExportExcel}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white rounded-lg text-xs font-semibold shadow-md shadow-emerald-900/30 transition cursor-pointer"
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              Excelga yuklab olish
            </button>
          )}

          {onExportPdf && (
            <button
              onClick={onExportPdf}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-700 hover:bg-rose-600 text-white rounded-lg text-xs font-semibold shadow-md shadow-rose-900/30 transition cursor-pointer"
            >
              <FileDown className="w-3.5 h-3.5" />
              PDF chop etish
            </button>
          )}
        </div>
      </div>

      {/* Table Container */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {/* Sticky Table Header */}
        <div className="bg-slate-950 border-b border-slate-800 text-[11px] font-bold text-slate-300 uppercase tracking-wider flex">
          {columns.map((col, idx) => (
            <div
              key={idx}
              style={{ width: col.width || `${100 / columns.length}%` }}
              className={`py-3 px-3 text-${col.align || "left"} shrink-0 select-none flex items-center gap-1`}
            >
              <span>{col.header}</span>
            </div>
          ))}
        </div>

        {/* Virtualized Body */}
        <div ref={parentRef} className="flex-1 overflow-auto bg-slate-900/40 divide-y divide-slate-800/60">
          <div
            style={{
              height: `${rowVirtualizer.getTotalSize()}px`,
              width: "100%",
              position: "relative",
            }}
          >
            {rowVirtualizer.getVirtualItems().map((virtualRow) => {
              const row = filteredData[virtualRow.index];
              return (
                <div
                  key={virtualRow.index}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    height: `${virtualRow.size}px`,
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                  className="flex items-center hover:bg-blue-600/10 transition border-b border-slate-800/40 text-xs text-slate-200"
                >
                  {columns.map((col, cIdx) => (
                    <div
                      key={cIdx}
                      style={{ width: col.width || `${100 / columns.length}%` }}
                      className={`px-3 py-2 text-${col.align || "left"} truncate shrink-0`}
                    >
                      {col.cell ? col.cell(row) : row[col.accessorKey as string]}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>

          {filteredData.length === 0 && (
            <div className="py-12 text-center text-xs text-slate-400">
              Ma'lumotlar topilmadi.
            </div>
          )}
        </div>

        {/* Totals Summary Footer */}
        {totalsRow && (
          <div className="p-3 bg-slate-950 border-t border-slate-800 text-xs font-bold text-slate-200">
            {totalsRow}
          </div>
        )}
      </div>
    </div>
  );
}
export default VirtualizedDataTable;

import type { ColumnDef } from "@tanstack/react-table"

import type { BookingPublic, BookingStatus } from "@/client"
import { Badge } from "@/components/ui/badge"
import { BookingActionsMenu } from "./BookingActionsMenu"

export type BookingTableData = BookingPublic & {
  venueName: string
  canDecide: boolean
  canCancel: boolean
  canDelete: boolean
}

const statusVariant: Record<
  BookingStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  pending: "secondary",
  approved: "default",
  rejected: "destructive",
  cancelled: "outline",
}

function formatDateTime(value: string) {
  return value.slice(0, 16).replace("T", " ")
}

export const columns: ColumnDef<BookingTableData>[] = [
  {
    accessorKey: "venueName",
    header: "Venue",
    cell: ({ row }) => (
      <span className="font-medium">{row.original.venueName}</span>
    ),
  },
  {
    id: "time",
    header: "Time",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {formatDateTime(row.original.start_time)} -{" "}
        {formatDateTime(row.original.end_time).slice(-5)}
      </span>
    ),
  },
  {
    accessorKey: "purpose",
    header: "Purpose",
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.purpose}</span>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <Badge variant={statusVariant[row.original.status]}>
        {row.original.status}
      </Badge>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => {
      const canDecide = row.original.canDecide
      const canCancel = row.original.canCancel
      const canDelete = row.original.canDelete
      if (!canDecide && !canCancel && !canDelete) {
        return null
      }
      return (
        <div className="flex justify-end">
          <BookingActionsMenu
            booking={row.original}
            canDecide={canDecide}
            canCancel={canCancel}
            canDelete={canDelete}
          />
        </div>
      )
    },
  },
]

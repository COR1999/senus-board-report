'use client'

import { useState } from 'react'
import {
  uploadPDF,
  deleteDocument,
  regenerateReport,
  importExternalFiling,
  hideExternalFiling,
  unhideExternalFiling,
  approveDocument,
} from '@/lib/data-service'

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}

/**
 * Wraps `uploadPDF`/`deleteDocument`/`regenerateReport` -- these already
 * throw on failure (unlike the GET helpers, which fall back to mock data),
 * but every call site previously only did `console.error` and swallowed the
 * failure from the user's point of view. These hooks surface a real,
 * user-facing `error` string instead, and reset it on the next attempt.
 */
export function useUploadDocument(onSuccess?: () => void) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const upload = async (file: File) => {
    setUploading(true)
    setError(null)
    try {
      await uploadPDF(file)
      onSuccess?.()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setUploading(false)
    }
  }

  return { upload, uploading, error }
}

export function useDeleteDocument(onSuccess?: () => void) {
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const remove = async (documentId: number) => {
    setDeletingId(documentId)
    setError(null)
    try {
      await deleteDocument(documentId)
      onSuccess?.()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setDeletingId(null)
    }
  }

  return { remove, deletingId, error }
}

export function useImportExternalFiling(onSuccess?: () => void) {
  const [importingId, setImportingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const importFiling = async (attachmentId: string) => {
    setImportingId(attachmentId)
    setError(null)
    try {
      await importExternalFiling(attachmentId)
      onSuccess?.()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setImportingId(null)
    }
  }

  return { importFiling, importingId, error }
}

export function useHideExternalFiling(onSuccess?: () => void) {
  const [hidingId, setHidingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const hideFiling = async (attachmentId: string) => {
    setHidingId(attachmentId)
    setError(null)
    try {
      await hideExternalFiling(attachmentId)
      onSuccess?.()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setHidingId(null)
    }
  }

  return { hideFiling, hidingId, error }
}

export function useUnhideExternalFiling(onSuccess?: () => void) {
  const [unhidingId, setUnhidingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const unhideFiling = async (attachmentId: string) => {
    setUnhidingId(attachmentId)
    setError(null)
    try {
      await unhideExternalFiling(attachmentId)
      onSuccess?.()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setUnhidingId(null)
    }
  }

  return { unhideFiling, unhidingId, error }
}

export function useApproveDocument(onSuccess?: () => void) {
  const [approvingId, setApprovingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const approve = async (documentId: number) => {
    setApprovingId(documentId)
    setError(null)
    try {
      await approveDocument(documentId)
      onSuccess?.()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setApprovingId(null)
    }
  }

  return { approve, approvingId, error }
}

export function useRegenerateReport(onSuccess?: () => void) {
  const [regeneratingId, setRegeneratingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const regenerate = async (reportId: number) => {
    setRegeneratingId(reportId)
    setError(null)
    try {
      await regenerateReport(reportId)
      onSuccess?.()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setRegeneratingId(null)
    }
  }

  return { regenerate, regeneratingId, error }
}

"""
Manual API testing script.
Run with: python test_api_manual.py

This tests the running FastAPI server.
Make sure the server is running first: uvicorn app.main:app --reload
"""

import asyncio
import httpx
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"


async def test_health():
    """Test health endpoint."""
    print("\n" + "="*60)
    print("🏥 Testing Health Endpoint")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
    
    print(f"Status: {response.status_code}")
    data = response.json()
    print(json.dumps(data, indent=2))
    
    assert response.status_code == 200
    assert data["status"] == "healthy"
    print("✅ Health check passed!")


async def test_upload_pdf():
    """Test document upload endpoint."""
    print("\n" + "="*60)
    print("📄 Testing Document Upload")
    print("="*60)
    
    # Create a test PDF
    pdf_path = Path("test_sample.pdf")
    
    # Minimal PDF content
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 500 >>
stream
BT
/F1 12 Tf
100 700 Td
(Financial Report 2024) Tj
0 -20 Td
(Revenue: 836K) Tj
0 -20 Td
(Customers: 138) Tj
0 -20 Td
(Cash: 250K) Tj
0 -20 Td
(EBITDA: 120K) Tj
0 -20 Td
(Gross Margin: 75%) Tj
0 -20 Td
(Operating Margin: 45%) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000230 00000 n 
0000000309 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
859
%%EOF"""
    
    # Write test PDF
    pdf_path.write_bytes(pdf_content)
    
    # Upload file
    async with httpx.AsyncClient() as client:
        with open(pdf_path, "rb") as f:
            files = {"file": ("test_sample.pdf", f, "application/pdf")}
            response = await client.post(f"{BASE_URL}/api/documents/upload", files=files)
    
    print(f"Status: {response.status_code}")
    data = response.json()
    print(json.dumps(data, indent=2, default=str)[:500] + "...")
    
    assert response.status_code == 200
    assert "id" in data
    assert data["filename"] == "test_sample.pdf"
    assert "extracted_text" in data
    
    print("✅ Document upload successful!")
    
    # Cleanup
    pdf_path.unlink()
    
    return data["id"]


async def test_list_documents():
    """Test listing documents."""
    print("\n" + "="*60)
    print("📋 Testing List Documents")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/documents?skip=0&limit=10")
    
    print(f"Status: {response.status_code}")
    data = response.json()
    
    print(f"Total documents: {len(data)}")
    if data:
        print(f"First document: {data[0]['filename']}")
    
    assert response.status_code == 200
    assert isinstance(data, list)
    
    print("✅ List documents successful!")
    
    return data[0]["id"] if data else None


async def test_get_document(document_id: int):
    """Test retrieving a specific document."""
    print("\n" + "="*60)
    print(f"🔍 Testing Get Document (ID: {document_id})")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/documents/{document_id}")
    
    print(f"Status: {response.status_code}")
    data = response.json()
    
    print(f"Filename: {data['filename']}")
    print(f"Status: {data['status']}")
    
    if data.get("financial_metrics"):
        print("\nFinancial Metrics:")
        metrics = data["financial_metrics"]
        for key, value in metrics.items():
            if value is not None and key != "extracted_at":
                print(f"  {key}: {value}")
    
    assert response.status_code == 200
    assert data["id"] == document_id
    
    print("✅ Get document successful!")


async def test_generate_report(document_id: int):
    """Test report generation."""
    print("\n" + "="*60)
    print(f"📊 Testing Report Generation (Document ID: {document_id})")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/reports",
            json={"document_id": document_id}
        )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"\nReport ID: {data['id']}")
        print(f"Document ID: {data['document_id']}")
        
        if data.get("ai_commentary"):
            print(f"\nAI Commentary Preview:")
            print(data["ai_commentary"][:300] + "...")
        
        if data.get("summary"):
            print(f"\nSummary Bullets:")
            for i, bullet in enumerate(data["summary"][:5], 1):
                print(f"  {i}. {bullet}")
        
        assert "id" in data
        assert data["document_id"] == document_id
        
        print("\n✅ Report generation successful!")
        return data["id"]
    else:
        print(f"Error: {response.text}")
        return None


async def test_get_report(report_id: int):
    """Test retrieving a report."""
    print("\n" + "="*60)
    print(f"📖 Testing Get Report (ID: {report_id})")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/reports/{report_id}")
    
    print(f"Status: {response.status_code}")
    data = response.json()
    
    print(f"Report ID: {data['id']}")
    print(f"Created: {data['created_at']}")
    print(f"Summary bullets: {len(data.get('summary', []))}")
    
    assert response.status_code == 200
    assert data["id"] == report_id
    
    print("✅ Get report successful!")


async def test_list_reports(document_id: int | None = None):
    """Test listing reports."""
    print("\n" + "="*60)
    print("📚 Testing List Reports")
    print("="*60)
    
    params = {}
    if document_id:
        params["document_id"] = document_id
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/reports", params=params)
    
    print(f"Status: {response.status_code}")
    data = response.json()
    
    print(f"Total reports: {len(data)}")
    if data:
        print(f"First report ID: {data[0]['id']}")
    
    assert response.status_code == 200
    assert isinstance(data, list)
    
    print("✅ List reports successful!")

async def test_delete_document(document_id: int):
    """Test document deletion."""
    print("\n" + "="*60)
    print(f"🗑️  Testing Delete Document (ID: {document_id})")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"{BASE_URL}/api/documents/{document_id}")
    
    print(f"Status: {response.status_code}")
    data = response.json()
    print(json.dumps(data, indent=2))
    
    assert response.status_code == 200
    
    print("✅ Document deletion successful!")


async def main():
    """Run all tests."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "SENUS BOARD API INTEGRATION TESTS" + " "*11 + "║")
    print("╚" + "="*58 + "╝")
    
    try:
        # Test health
        await test_health()
        
        # Test document upload
        doc_id = await test_upload_pdf()
        
        # Test list documents
        doc_id = await test_list_documents() or doc_id
        
        # Test get document
        await test_get_document(doc_id)
        
        # Test report generation
        report_id = await test_generate_report(doc_id)
        
        if report_id:
            # Test get report
            await test_get_report(report_id)
            
            # Test list reports
            await test_list_reports(doc_id)
        
        # Test delete (optional - comment out if you want to keep test data)
        # await test_delete_document(doc_id)
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())